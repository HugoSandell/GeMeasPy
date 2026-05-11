"""CLI script to perform testing and mutation analysis."""

import argparse
import asyncio
import contextlib
import io
import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable
from pathlib import Path
from threading import Event, Thread

import aiohttp

import cosmic_ray.config
import cosmic_ray.modules as cr_modules
from cosmic_ray import work_db
from cosmic_ray.commands.execute import execute as cr_execute
from cosmic_ray.commands.init import init as cr_init
from cosmic_ray.config import ConfigDict
from cosmic_ray.distribution.http import run_worker
from cosmic_ray.tools.filters import operators_filter, pragma_no_mutate
from cosmic_ray.work_db import MutationSpec, TestOutcome, WorkDB, WorkerOutcome

import gemeaspy
from gemeaspy.tests import _logging


def _setup_worker_sandbox(sandbox_dir: Path, root_dir: Path) -> None:
    """Copy the entire gemeaspy source directory into sandbox_dir.

    Each worker runs with cwd=sandbox_dir, so relative module paths (e.g.
    "gemeaspy/acquisition/session.py") resolve inside the sandbox.  Python's
    sys.path starts with '' (= cwd), so pytest subprocesses import gemeaspy
    from the sandbox, eliminating file-system race conditions between 
    concurrent workers.
    """
    shutil.copytree(
        str(root_dir / "gemeaspy"),
        str(sandbox_dir / "gemeaspy"),
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


def _run_worker_sandboxed(port: int, sandbox_dir: str) -> None:
    """Start a cosmic-ray HTTP worker isolated in its own sandbox directory.

    Changing cwd to sandbox_dir before starting the server means:
    - Incoming relative module_path values resolve to sandbox copies.
    - The pytest subprocess inherits cwd=sandbox_dir, so '' on sys.path
      points there and Python imports gemeaspy from the sandbox.
    """
    os.chdir(sandbox_dir)
    run_worker(port=port)


def _progress_reporter(db: WorkDB, end_event: Event):
    """Repeatedly report status until all work is done. 
    Terminates early when end_event is set.
    """
    num_items = len(db.pending_work_items)
    start = time.monotonic()
    last_tick = start
    last_done = 0
    eta_s: float | None = None
    while len(db.pending_work_items) > 0 and not end_event.is_set():
        time.sleep(1.0)
        now = time.monotonic()
        tick_elapsed = now - last_tick
        last_tick = now
        done = num_items - len(db.pending_work_items)
        if done > last_done:
            eta_s = (now - start) / done * len(db.pending_work_items)
            last_done = done
        elif eta_s is not None:
            eta_s = max(0.0, eta_s - tick_elapsed)
        if eta_s is None:
            eta_str = ""
        elif eta_s <= 0:
            eta_str = "  Any time now..."
        else:
            eta_buffered = eta_s + 10
            eta_str = f"  ETA {int(eta_buffered // 60)}m{int(eta_buffered % 60):02d}s"
        width = os.get_terminal_size().columns
        msg = f"\rRunning work item {done}/{num_items}{eta_str}"
        print("\r" + (" " * width) + msg, end="")
    print()


def _mutation_fingerprint(mutation: MutationSpec) -> tuple[str, str, int]:
    """Stable mutation identifier across runs: (module_path, operator_name, occurrence)."""
    return (str(mutation.module_path), mutation.operator_name, mutation.occurrence)


def load_equivalent_fingerprints(data_dir: str) -> set[tuple[str, str, int]]:
    """Load manually tagged equivalent mutants from equivalent_mutants.json.

    The JSON file is a list of objects with keys:
      module_path   - relative path as shown by cosmic-ray (e.g. "gemeaspy/acquisition/session.py")
      operator_name - cosmic-ray operator string (e.g. "core/ReplaceComparisonOperator")
      occurrence    - zero-based occurrence index of that operator in the module
      reason        - (optional) manual note, not used in calculation

    Returns a set of (module_path, operator_name, occurrence) tuples.
    """
    equiv_file = os.path.join(data_dir, "equivalent_mutants.json")
    if not os.path.isfile(equiv_file):
        return set()
    with open(equiv_file, encoding="utf-8") as f:
        entries = json.load(f)
    return {(e["module_path"], e["operator_name"], e["occurrence"]) for e in entries}


def run_baseline_coverage(
    python_path: str,
    generator: str,
    pytest_args: list[str],
    log_file: str,
    data_dir: str,
) -> tuple[dict[str, set[int]], float]:
    """Run the test suite once to collect baseline line coverage and measure its duration.

    Configures coverage.py so that acquisition subprocesses spawned by the tests
    also contribute coverage data.
    Returns ({absolute_filepath: {covered_line_numbers}}, elapsed_seconds).
    The coverage dict is {} on failure; elapsed_seconds is always set.
    """
    data_file = os.path.abspath(os.path.join(data_dir, f"baseline_{generator}.coverage"))
    json_file  = os.path.abspath(os.path.join(data_dir, f"baseline_{generator}_coverage.json"))
    coveragerc = os.path.abspath(os.path.join(data_dir, f"baseline_{generator}.coveragerc"))

    with open(coveragerc, "w", encoding="utf-8") as f:
        f.write(
            "[run]\n"
            "source = gemeaspy/acquisition\n"
            "branch = True\n"
            "parallel = True\n"
            "patch = subprocess\n"
            f"data_file = {data_file}\n"
        )

    env = {**os.environ, "COVERAGE_PROCESS_START": coveragerc}
    t0 = time.monotonic()
    subprocess.run(
        [
            python_path,
            "-m",
            "coverage",
            "run",
            f"--rcfile={coveragerc}",
            "-m",
            "pytest",
            *pytest_args,
            f"--generator={generator}",
            f"--log-file={log_file}",
        ],
        env=env,
    )
    elapsed = time.monotonic() - t0

    # Merge parallel .coverage.* files created by the main process and subprocesses.
    subprocess.run(
        [python_path, "-m", "coverage", "combine", f"--rcfile={coveragerc}"],
        cwd=data_dir,
        check=False,
    )
    subprocess.run(
        [python_path, "-m", "coverage", "json",
         f"--rcfile={coveragerc}", f"--data-file={data_file}", "-o", json_file],
        check=False,
    )

    if not os.path.isfile(json_file):
        print("Warning: baseline coverage JSON not generated - skipping coverage-based flagging.")
        return {}, elapsed

    with open(json_file, encoding="utf-8") as f:
        cov_data = json.load(f)

    covered: dict[str, set[int]] = {}
    for filepath, file_data in cov_data.get("files", {}).items():
        covered[str(Path(filepath).resolve())] = set(file_data.get("executed_lines", []))

    acq_count = sum(1 for p in covered if "acquisition" in p)
    if acq_count == 0:
        print("Warning: no acquisition module lines in coverage data.")
        print("  The acquisition subprocess may not have reported coverage.")
        print("  Ensure 'coverage' is installed in the active venv and COVERAGE_PROCESS_START is readable.")
        return {}, elapsed

    print(f"  Baseline coverage: {acq_count} acquisition module(s) tracked.")
    return covered, elapsed


def _is_covered(mutation: MutationSpec, covered: dict[str, set[int]]) -> bool:
    module_abs = str(mutation.module_path.resolve())
    return module_abs in covered and mutation.start_pos[0] in covered[module_abs]


def write_review_report(
    db: WorkDB,
    generator: str,
    data_dir: str,
    equivalent_fingerprints: set[tuple[str, str, int]],
    covered: dict[str, set[int]],
):
    """Write survived, non-equivalent mutants to a text file for manual review.

    Each entry shows the module, line, operator, and diff.
    Mutants whose lines have no coverage data are tagged [UNCOVERED]; they are excluded
    from the covered score but counted as unkilled in the full score.
    To mark a mutant as equivalent, add its fingerprint to equivalent_mutants.json.
    """
    report_path = os.path.join(data_dir, f"survived_review_{generator}.txt")
    count = 0
    with open(report_path, "w", encoding="utf-8") as f:
        for work_item, result in db.completed_work_items:
            if result.test_outcome != TestOutcome.SURVIVED:
                continue
            for mutation in work_item.mutations:
                if _mutation_fingerprint(mutation) in equivalent_fingerprints:
                    continue
                tags: list[str] = []
                if covered and not _is_covered(mutation, covered):
                    tags.append("UNCOVERED")
                tag_str = f" [{', '.join(tags)}]" if tags else ""
                f.write(
                    f"=== {mutation.module_path}:{mutation.start_pos[0]}"
                    f"{tag_str} | {mutation.operator_name} #{mutation.occurrence} ===\n"
                )
                if result.diff:
                    f.write(result.diff.strip())
                    f.write("\n")
                f.write("\n")
                count += 1
    print(f"Review report: {report_path} ({count} survived mutant(s) to review)")


def print_summary(
    db: WorkDB,
    equivalent_fingerprints: set[tuple[str, str, int]],
    covered: dict[str, set[int]],
):
    """Summarise and print the results of a WorkDB."""
    results = list(db.completed_work_items)
    total = len(results)

    num_killed      = sum(1 for _, r in results if r.test_outcome == TestOutcome.KILLED)
    num_timeout     = sum(1 for _, r in results if r.test_outcome == TestOutcome.KILLED and r.output == "timeout")
    num_survived    = sum(1 for _, r in results if r.test_outcome == TestOutcome.SURVIVED)
    num_incompetent = sum(1 for _, r in results if r.test_outcome == TestOutcome.INCOMPETENT)
    num_no_test     = sum(1 for _, r in results if r.worker_outcome == WorkerOutcome.NO_TEST)
    num_abnormal    = sum(1 for _, r in results if r.worker_outcome == WorkerOutcome.ABNORMAL)
    num_skipped     = sum(1 for _, r in results if r.worker_outcome == WorkerOutcome.SKIPPED)

    num_equivalent = 0
    num_uncovered  = 0
    for work_item, result in results:
        if result.test_outcome != TestOutcome.SURVIVED:
            continue
        for mutation in work_item.mutations:
            if _mutation_fingerprint(mutation) in equivalent_fingerprints:
                num_equivalent += 1
            elif covered and not _is_covered(mutation, covered):
                num_uncovered += 1

    # covered_denom: excludes equivalent and uncovered - only mutants the suite could
    # realistically kill. This is the primary score.
    # full_denom: excludes only equivalent - treats uncovered mutants as survivable gaps,
    # giving a lower bound that penalises missing coverage.
    # Both exclude incompetent, NO_TEST, ABNORMAL, and SKIPPED (no meaningful test outcome).
    covered_denom = num_killed + num_survived - num_equivalent - num_uncovered
    full_denom    = num_killed + num_survived - num_equivalent
    covered_score = num_killed / covered_denom if covered_denom > 0 else 0.0
    full_score    = num_killed / full_denom    if full_denom    > 0 else 0.0

    def pct(n) -> str:
        return f"{n / total:.1%}" if total else "N/A"
    print(f"Killed:       {num_killed} ({pct(num_killed)})")
    if num_timeout:
        print(f"  Timeout:    {num_timeout}")
    print(f"Survived:     {num_survived} ({pct(num_survived)})")
    if num_equivalent or num_uncovered:
        # Indented because they are a subset of the total number of surviving mutants
        print(f"  Equivalent: {num_equivalent}")
        print(f"  Uncovered:  {num_uncovered}")
    print(f"Incompetent:  {num_incompetent} ({pct(num_incompetent)})")
    print(f"Untested:     {num_no_test} ({pct(num_no_test)})")
    print(f"Abnormal:     {num_abnormal} ({pct(num_abnormal)})")
    print(f"Skipped:      {num_skipped} ({pct(num_skipped)})")
    print(f"Mutation score (covered):  {covered_score:.1%} ({num_killed}/{covered_denom})")
    print(f"Mutation score (full):     {full_score:.1%} ({num_killed}/{full_denom})")


def _generate_and_run_test_suite(
    generator: str,
    generator_args: list[str],
    config: ConfigDict,
    modules_to_mutate: Iterable[Path],
    equivalent_fingerprints: set[tuple[str, str, int]],
    python_path: str,
    pytest_log_file: str,
    data_dir: str,
    cr_config_file: str,
    pytest_test_dir: str,
    root_dir: str,
):
    print(f"Running mutation analysis on test case generator '{generator}'")
    # Workers run with cwd=sandbox_dir, so we must give pytest an absolute path
    # to the test directory and explicitly set --rootdir so that conftest.py at
    # the project root is still discovered.
    config["test-command"] = (
        f"\"{python_path}\" "
        f"-m pytest \"{pytest_test_dir}\" "
        f"--rootdir=\"{root_dir}\" "
        f"{' '.join(generator_args)} "
        f"--generator={generator} "
        f"--log-file=\"{pytest_log_file}\""
    )


    cr_session_file = os.path.join(data_dir, f"cosmicray_{generator}.sqlite")
    if os.path.isfile(cr_session_file):
        os.remove(cr_session_file)

    start_time = time.monotonic()
    with work_db.use_db(cr_session_file, mode=WorkDB.Mode.create) as db:
        print("Initialising WorkDB")
        cr_init(modules_to_mutate, work_db=db, operator_cfgs={})
        print(f"Created {db.num_work_items} work items.")
        print("Filtering...")
        operators_filter.main((cr_session_file, cr_config_file))
        with contextlib.redirect_stdout(io.StringIO()): # pragma_no_mutate is noisy!
            pragma_no_mutate.main((cr_session_file,))
        print(f"Collecting baseline coverage for '{generator}'...")
        covered, baseline_time = run_baseline_coverage(
            python_path, generator, generator_args, pytest_log_file, data_dir,
        )
        config["timeout"] = baseline_time * 5
        print(f"  Baseline time: {baseline_time:.1f}s; timeout set to {config['timeout']:.1f}s")
        print(f"Executing {len(db.pending_work_items)} work items...")
        report_end_event = Event()
        report_thread = Thread(target=_progress_reporter, args=(db, report_end_event), daemon=True)
        report_thread.start()
        cr_execute(work_db=db, config=config)
        report_end_event.set()
        report_thread.join(5)
        if report_thread.is_alive():
            _logging.warning("Progress reporter didn't exit after all work items were executed.")

        print(f"Done with session: {cr_session_file}")
        print_summary(db, equivalent_fingerprints, covered)
        write_review_report(db, generator, data_dir, equivalent_fingerprints, covered)

    execution_time = time.monotonic() - start_time
    print(f"'{generator}' done in {execution_time:.1f} seconds.")


def _acts_suite_size(python_path: str, pytest_test_dir: str, root_dir: str, strength: int) -> int:
    result = subprocess.run(
        [python_path, "-m", "pytest", pytest_test_dir,
         f"--rootdir={root_dir}", "--generator=acts", f"--strength={strength}",
         "--collect-only", "-q", "--no-header", "--maxfail=1"],
        capture_output=True, text=True,
    )
    return sum(1 for line in result.stdout.splitlines() if "::" in line)


def _find_min_acts_strength_above(
    python_path: str, pytest_test_dir: str, root_dir: str, min_size: int
) -> tuple[int, int] | None:
    """Return (strength, suite_size) for the smallest acts suite with size > min_size, or None."""
    for strength in range(1, 7):
        size = _acts_suite_size(python_path, pytest_test_dir, root_dir, strength)
        if size > min_size:
            return strength, size
    return None


def _physical_cpu_count() -> int:
    """Tries to return physical core count."""
    try:
        import psutil # type: ignore[import]
        n = psutil.cpu_count(logical=False)
        if n:
            return n
    except ImportError:
        pass
    return multiprocessing.cpu_count() # Fallback


def _start_workers(
    worker_count: int,
    root_dir: str,
    port_base: int,
) -> tuple[list[str], list[multiprocessing.Process], list[Path]]:
    """Start worker_count HTTP worker processes and return (urls, processes, sandbox_dirs)."""
    ports = [port_base + i for i in range(worker_count)]
    sandbox_dirs: list[Path] = []
    workers: list[multiprocessing.Process] = []
    for i, port in enumerate(ports):
        sandbox = Path(tempfile.mkdtemp(prefix=f"cr_worker_{port_base - 55430 + i}_"))
        sandbox_dirs.append(sandbox)
        _setup_worker_sandbox(sandbox, Path(root_dir))
        worker = multiprocessing.Process(target=_run_worker_sandboxed, args=(port, str(sandbox)))
        workers.append(worker)
        worker.start()
    urls = [f"http://localhost:{port}" for port in ports]
    return urls, workers, sandbox_dirs


def _stop_workers(
    workers: list[multiprocessing.Process],
    sandbox_dirs: list[Path],
) -> None:
    """Terminate all worker processes and remove their sandbox directories."""
    for worker in workers:
        try:
            worker.terminate()
            worker.join(5)
            worker.close()
        except Exception:
            pass
    for sandbox in sandbox_dirs:
        shutil.rmtree(str(sandbox), ignore_errors=True)


def _run_baseline_check(
    generator: str,
    generator_args: list[str],
    python_path: str,
    pytest_test_dir: str,
    root_dir: str,
    pytest_log_file: str,
    worker_urls: list[str],
    worker_count: int,
) -> None:
    """Run 2 * worker_count unmodified test-suite passes through the worker pool.

    Each pass applies no mutations, so every run should report SURVIVED.  Any
    failure indicates that the worker infrastructure (sandboxing, port
    assignment, concurrent I/O) is interfering with the tests.
    """
    num_runs = 2 * worker_count
    test_command = (
        f"\"{python_path}\" "
        f"-m pytest \"{pytest_test_dir}\" "
        f"--rootdir=\"{root_dir}\" "
        f"{' '.join(generator_args)} "
        f"--generator={generator} "
        f"--log-file=\"{pytest_log_file}\""
    )

    print(f"Benchmarking '{generator}' suite...")
    t0 = time.monotonic()
    subprocess.run(
        [python_path, "-m", "pytest", pytest_test_dir,
         f"--rootdir={root_dir}", *generator_args, f"--generator={generator}",
         f"--log-file={pytest_log_file}"],
        capture_output=True,
    )
    benchmark_time = time.monotonic() - t0
    timeout = benchmark_time * 3
    print(f"  Benchmark: {benchmark_time:.1f}s; timeout: {timeout:.1f}s")
    print(f"Running {num_runs} baseline passes ({worker_count} workers)...")

    async def _post(session: aiohttp.ClientSession, url: str) -> dict:
        params = {"mutations": [], "test_command": test_command, "timeout": timeout}
        try:
            async with session.post(url, json=params) as resp:
                return await resp.json()
        except Exception as exc:
            return {"worker_outcome": "abnormal", "test_outcome": None,
                    "output": str(exc), "diff": None}

    async def _run_all() -> list[dict]:
        results: list[dict] = []
        available = list(worker_urls)
        in_flight: dict[asyncio.Task, str] = {}
        async with aiohttp.ClientSession() as session:
            for _ in range(num_runs):
                while not available:
                    done, _ = await asyncio.wait(in_flight.keys(), return_when=asyncio.FIRST_COMPLETED)
                    for task in done:
                        available.append(in_flight.pop(task))
                        results.append(task.result())
                url = available.pop()
                task = asyncio.create_task(_post(session, url))
                in_flight[task] = url
            while in_flight:
                done, _ = await asyncio.wait(in_flight.keys(), return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    available.append(in_flight.pop(task))
                    results.append(task.result())
        return results

    results = asyncio.run(_run_all())

    passed = sum(1 for r in results if r.get("test_outcome") == "survived")
    failed = num_runs - passed
    if failed == 0:
        print(f"  All {num_runs} baseline passes passed.")
    else:
        print(f"  {failed}/{num_runs} baseline passes FAILED:")
        for i, r in enumerate(results):
            if r.get("test_outcome") != "survived":
                out = (r.get("output") or "").strip().splitlines()
                tail = out[-1] if out else "(no output)"
                print(f"    Run {i + 1}: {r.get('worker_outcome')} | {tail}")


def main():
    ROOTPKG_DIR = os.path.split(gemeaspy.__file__)[0]
    ROOT_DIR = os.path.split(ROOTPKG_DIR)[0]
    DATA_DIR = os.path.join(ROOT_DIR, "test_data")
    CR_CONFIG_FILE = os.path.join(ROOT_DIR, "cosmic-ray.toml")
    PYTEST_LOG_FILE = os.path.join(DATA_DIR, "mutation_pytest.log")
    PYTEST_TEST_DIR = os.path.join(ROOTPKG_DIR, "tests")
    # Getting the absolute path fixes an issue where subprocess.run in cosmic-ray
    # executes the wrong python executable
    PYTHON_PATH = sys.executable
    parser = argparse.ArgumentParser(description="Run mutation analysis")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--size", type=int, metavar="N", help="Run random(--size=N) and the smallest acts suite above that size")
    group.add_argument("--strength", type=int, metavar="N", help="Run acts(--strength=N) and random with the resulting suite size")
    parser.add_argument("--only", choices=["random", "acts"], metavar="{random,acts}", help="Restrict to a single generator")
    parser.add_argument("--workers", type=int, default=None, metavar="N", help="Number of HTTP workers (default: cpu count)")
    parser.add_argument("--verify-baseline", dest="baseline", action="store_true", help="Run baseline verification instead of mutation analysis: sends 2 * workers unmodified test passes through the worker pool")
    args = parser.parse_args()

    if args.size is not None:
        generators_to_run = [("random", [f"--size={args.size}"])]
        if args.only != "random":
            print(f"Searching for smallest acts suite above size {args.size}...")
            found = _find_min_acts_strength_above(PYTHON_PATH, PYTEST_TEST_DIR, ROOT_DIR, args.size)
            if found is not None:
                strength, acts_size = found
                print(f"  Found: strength={strength} yields {acts_size} test cases.")
                generators_to_run.append(("acts", [f"--strength={strength}"]))
            else:
                print(f"  No acts suite found above size {args.size} (tried strength 1-6); skipping acts.")
        if args.only == "acts":
            generators_to_run = [g for g in generators_to_run if g[0] == "acts"]
    else:
        acts_size = _acts_suite_size(PYTHON_PATH, PYTEST_TEST_DIR, ROOT_DIR, args.strength)
        print(f"Acts suite at strength={args.strength}: {acts_size} test cases.")
        generators_to_run = [
            ("acts", [f"--strength={args.strength}"]),
            ("random", [f"--size={acts_size}"]),
        ]
        if args.only is not None:
            generators_to_run = [g for g in generators_to_run if g[0] == args.only]

    config: ConfigDict = cosmic_ray.config.load_config(CR_CONFIG_FILE)
    config["distributor"]["name"] = "http"

    modules_to_mutate: list[Path] = []
    equivalent_fingerprints: set[tuple[str, str, int]] = set()

    if not args.baseline:
        module_paths: list[Path] = [Path("gemeaspy/acquisition")]
        excluded_modules: list[str] = [
            "**/__init__.py",
            "**/__main__.py",
            "gemeaspy/acquisition/check_input.py",
            "gemeaspy/acquisition/subvision_relay.py",
        ]
        modules_to_mutate = list(cr_modules.filter_paths(
            cr_modules.find_modules(module_paths), excluded_modules
        ))
        config["module-path"] = module_paths
        config["excluded-modules"] = excluded_modules

    worker_count = args.workers if args.workers is not None else _physical_cpu_count()
    PORT_BASE = 55430
    if not "distributor" in config:
        config["distributor"] = {}
    if not "http" in config["distributor"]:
        config["distributor"]["http"] = {}

    worker_urls, workers, sandbox_dirs = _start_workers(worker_count, ROOT_DIR, PORT_BASE)
    config["distributor"]["http"]["worker-urls"] = worker_urls

    os.makedirs(DATA_DIR, exist_ok=True)

    if not args.baseline:
        equivalent_fingerprints = load_equivalent_fingerprints(DATA_DIR)
        if equivalent_fingerprints:
            print(f"Loaded {len(equivalent_fingerprints)} equivalent mutant fingerprint(s).")

    try:
        for generator, generator_args in generators_to_run:
            if args.baseline:
                _run_baseline_check(
                    generator, generator_args,
                    PYTHON_PATH, PYTEST_TEST_DIR, ROOT_DIR, PYTEST_LOG_FILE,
                    worker_urls, worker_count,
                )
            else:
                _generate_and_run_test_suite(
                    generator, generator_args, config,
                    modules_to_mutate, equivalent_fingerprints,
                    PYTHON_PATH, PYTEST_LOG_FILE, DATA_DIR, CR_CONFIG_FILE,
                    PYTEST_TEST_DIR, ROOT_DIR,
                )
    finally:
        _stop_workers(workers, sandbox_dirs)

    if args.baseline:
        return

    equiv_file = os.path.join(DATA_DIR, "equivalent_mutants.json")
    print()
    print("Output files:")
    for generator, _ in generators_to_run:
        print(f"  [{generator}] session:       {os.path.join(DATA_DIR, f'cosmicray_{generator}.sqlite')}")
        print(f"  [{generator}] review report: {os.path.join(DATA_DIR, f'survived_review_{generator}.txt')}")
    print()
    print("Testing complete. Next steps for manual review:")
    print()
    print("  1. Open each review report listed above.")
    print("     Each entry has the form:")
    print("       === <module>:<line> [tags] | <operator> #<occurrence> ===")
    print("       <diff>")
    print()
    print("  2. Entries tagged [UNCOVERED] were never executed by the test suite.")
    print("     Two mutation scores are reported:")
    print("       covered: excludes uncovered mutants from the denominator (primary score).")
    print("       full:    includes uncovered mutants as unkilled - a lower bound that")
    print("                penalises missing coverage.")
    print("     Improving test coverage will raise both scores.")

    print()
    print("  3. For mutants that are semantically equivalent to the original,")
    print(f"     add an entry to {equiv_file}:")
    print('       { "module_path": "<module>", "operator_name": "<operator>",')
    print('         "occurrence": <occurrence>, "reason": "<why it is equivalent>" }')
    print("     The three fingerprint values are taken directly from the entry header.")
    print("     Equivalent mutants are excluded from the mutation score on the next run.")
    print()
    print("  4. Re-run with the same generators to see the updated mutation score.")


if __name__ == "__main__":
    main()
