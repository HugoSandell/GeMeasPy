"""CLI script to perform testing and mutation analysis."""

import argparse
import asyncio
import contextlib
import difflib
import glob
import http.server
import io
import json
import multiprocessing
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread

import aiohttp
import cosmic_ray.config
import cosmic_ray.modules as cr_modules
import psutil
from cosmic_ray import work_db
from cosmic_ray.commands.execute import execute as cr_execute
from cosmic_ray.commands.init import init as cr_init
from cosmic_ray.config import ConfigDict
from cosmic_ray.tools.filters import operators_filter, pragma_no_mutate
from cosmic_ray.work_db import MutationSpec, TestOutcome, WorkDB, WorkerOutcome, WorkResultStorage

import gemeaspy
from gemeaspy.tests.coverage_utils import is_covered_abs as _is_covered_abs
from gemeaspy.tests import _logging
from gemeaspy.tests.test_main import ACQUISITION_TIMEOUT
from gemeaspy.tests._sgr import (
    CLR_GREEN_FG,
    CLR_RED_FG,
    CLR_YELLOW_FG,
    STYLE_BOLD,
    STYLE_DIM,
    with_sgr,
)


def _setup_worker_sandbox(sandbox_dir: Path, root_dir: Path) -> None:
    """Copy the entire gemeaspy source directory into sandbox_dir.

    Each worker runs with cwd=sandbox_dir, so relative module paths (e.g. "gemeaspy/acquisition/session.py") resolve inside the sandbox.  
    Python's sys.path starts with '' (= cwd), so pytest subprocesses import gemeaspy from the sandbox, 
    eliminating file-system race conditions between concurrent workers.
    """
    shutil.copytree(
        str(root_dir / "gemeaspy"),
        str(sandbox_dir / "gemeaspy"),
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )


_TIMEOUT_TAG = "CR:TIMEOUT"
_VALID_FAIL_TAG = "CR:VALID_FAIL"
_INVALID_FAIL_TAG = "CR:INVALID_FAIL"

_incompetent_cache: dict[str, set[tuple]] = {}

def _incompetent_fingerprint(
    module_path: str,
    operator_name: str,
    original_code: str,
    mutated_code: str,
) -> tuple[str, str, int, tuple[str, ...]]:
    line = 0
    changed: list[str] = []
    for dl in difflib.unified_diff(original_code.splitlines(), mutated_code.splitlines(), lineterm=""):
        if dl.startswith("@@"):
            m = re.match(r"^@@ -(\d+)", dl)
            if m:
                line = int(m.group(1))
        elif dl.startswith(("+", "-")) and not dl.startswith(("---", "+++")):
            changed.append(dl)
    return (module_path, operator_name, line, tuple(changed))


def _load_incompetent_cache(cache_path: str) -> set[tuple]:
    if not os.path.isfile(cache_path):
        return set()
    try:
        with open(cache_path, encoding="utf-8") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, OSError):
        return set()
    return {(e["module_path"], e["operator"], e["line"], tuple(e["diff"])) for e in entries}


def _check_incompetent_cache(cache_path: str, fp: tuple) -> bool:
    if cache_path not in _incompetent_cache:
        _incompetent_cache[cache_path] = _load_incompetent_cache(cache_path)
    return fp in _incompetent_cache[cache_path]


def _record_incompetent(cache_path: str, fp: tuple) -> None:
    module_path, operator, line, diff_lines = fp
    if cache_path not in _incompetent_cache:
        _incompetent_cache[cache_path] = _load_incompetent_cache(cache_path)
    if fp in _incompetent_cache[cache_path]:
        return
    _incompetent_cache[cache_path].add(fp)
    try:
        with open(cache_path, encoding="utf-8") as f:
            entries = json.load(f)
    except (json.JSONDecodeError, OSError):
        entries = []
    entries.append({"module_path": module_path, "operator": operator, "line": line, "diff": list(diff_lines)})
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
        
        
def _merge_incompetent_caches() -> None:
    files = glob.glob("test_data/incompetent_mutants_W*.json")
    entries = []
    for filename in files:
        entries.extend(_load_incompetent_cache(filename))
    with open("test_data/incompetent_mutants.json", "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    for filename in files:
        os.unlink(filename)

def _error_lines(output: str) -> str:
    return "\n".join(
        line.rstrip("\r")
        for line in output.splitlines()
        if line.lstrip("\r").startswith("E ")
    )


def _run_worker_sandboxed(port: int, sandbox_dir: str, data_dir: str) -> None:
    """Start a cosmic-ray HTTP worker isolated in its own sandbox directory.

    Changing cwd to sandbox_dir before starting the server means:
    - Incoming relative module_path values resolve to sandbox copies.
    - The pytest subprocess inherits cwd=sandbox_dir, so '' on sys.path
      points there and Python imports gemeaspy from the sandbox.
    """
    os.chdir(sandbox_dir)
    _run_worker_threaded(port, data_dir)


def _run_worker_threaded(port: int, data_dir: str) -> None:
    """Threading-based HTTP worker that avoids ProactorEventLoop problems on Windows.
    ThreadingTCPServer runs each request in its own OS thread.
    """
    cache_path = os.path.join(data_dir, "incompetent_mutants.json")
    import cosmic_ray.plugins
    from cosmic_ray.mutating import mutate_and_test as _mutate_and_test
    from cosmic_ray.mutating import mutate_code as _mutate_code
    from cosmic_ray.util import read_python_source as _read_python_source
    from cosmic_ray.work_item import MutationSpec as _MutationSpec

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            mutations = [
                _MutationSpec(
                    module_path=Path(m["module_path"]),
                    operator_name=m["operator"],
                    occurrence=m["occurrence"],
                    start_pos=(0, 0),
                    end_pos=(0, 1),
                )
                for m in body["mutations"]
            ]

            def _build_result() -> dict:
                import warnings
                fingerprints: list[tuple] = []
                for mutation in mutations:
                    try:
                        operator_class = cosmic_ray.plugins.get_operator(mutation.operator_name)
                        try:
                            operator_args = mutation.operator_args
                        except AttributeError:
                            operator_args = {}
                        operator = operator_class(**operator_args)
                        original_code = _read_python_source(mutation.module_path)
                        mutated_code = _mutate_code(original_code, operator, mutation.occurrence)
                    except Exception:
                        continue  # can't pre-check this mutation; let _mutate_and_test handle it
                    if mutated_code is None:
                        continue
                    fp = _incompetent_fingerprint(
                        str(mutation.module_path), mutation.operator_name,
                        original_code, mutated_code,
                    )
                    fingerprints.append(fp)
                    if _check_incompetent_cache(cache_path, fp):
                        return {
                            "worker_outcome": WorkerOutcome.NORMAL.value,
                            "output": "Known incompetent (cached)",
                            "test_outcome": TestOutcome.INCOMPETENT.value,
                            "diff": None,
                        }
                    try:
                        with warnings.catch_warnings():
                            warnings.simplefilter("ignore", SyntaxWarning)
                            compile(mutated_code, str(mutation.module_path), "exec")
                    except SyntaxError as exc:
                        _record_incompetent(cache_path, fp)
                        return {
                            "worker_outcome": WorkerOutcome.NORMAL.value,
                            "output": f"SyntaxError in mutated {mutation.module_path}: {exc}",
                            "test_outcome": TestOutcome.INCOMPETENT.value,
                            "diff": None,
                        }
                result = _mutate_and_test(
                    mutations=mutations,
                    test_command=body["test_command"],
                    timeout=body["timeout"],
                )
                if result.test_outcome == TestOutcome.KILLED:
                    errors = _error_lines(result.output or "")
                    if _TIMEOUT_TAG in errors or (_VALID_FAIL_TAG not in errors and _INVALID_FAIL_TAG not in errors):
                        for fp in fingerprints:
                            _record_incompetent(cache_path, fp)
                        return {
                            "worker_outcome": result.worker_outcome.value,
                            "output": result.output,
                            "test_outcome": TestOutcome.INCOMPETENT.value,
                            "diff": result.diff,
                        }
                return {
                    "worker_outcome": result.worker_outcome.value,
                    "output": result.output,
                    "test_outcome": result.test_outcome.value if result.test_outcome is not None else None,
                    "diff": result.diff,
                }

            payload = json.dumps(_build_result()).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except OSError:
                pass  # client disconnected before we could send the response

    class _Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True

    with _Server(("", port), _Handler) as server:
        server.serve_forever()


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
    return (str(mutation.module_path).replace("\\", "/"), mutation.operator_name, mutation.occurrence)


def _load_fingerprints_json(path: str) -> set[tuple[str, str, int]]:
    """Load (module_path, operator_name, occurrence) fingerprints from a JSON classification file

    The JSON file is a list of objects with keys:
      module_path   - relative path as shown by cosmic-ray (e.g. "gemeaspy/acquisition/session.py")
      operator_name - cosmic-ray operator string (e.g. "core/ReplaceComparisonOperator")
      occurrence    - zero-based occurrence index of that operator in the module
      reason        - (optional) manual note, not used in calculation
    """
    if not os.path.isfile(path):
        return set()
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return {(str(e["module_path"]).replace("\\", "/"), e["operator_name"], e["occurrence"]) for e in entries}


def load_equivalent_fingerprints(data_dir: str) -> set[tuple[str, str, int]]:
    """Load manually tagged equivalent mutants from equivalent_mutants.json."""
    return _load_fingerprints_json(os.path.join(data_dir, "equivalent_mutants.json"))


def _fingerprints_from_review_report(path: str) -> set[tuple[str, str, int]]:
    """Parse fingerprints from a survived_review_*.txt file."""
    from gemeaspy.tests.review_mutants import parse_review_file
    if not os.path.isfile(path):
        return set()
    return {e.fingerprint() for e in parse_review_file(Path(path))}


def run_baseline_coverage(
    python_path: str,
    generator: str,
    label: str,
    pytest_args: list[str],
    log_file: str,
    data_dir: str,
    fresh: bool = False,
) -> tuple[dict[str, set[int]], float]:
    """Run the test suite once to collect baseline line coverage and measure its duration.

    Configures coverage.py so that acquisition subprocesses spawned by the tests
    also contribute coverage data.
    Returns ({absolute_filepath: {covered_line_numbers}}, elapsed_seconds).
    The coverage dict is {} on failure; elapsed_seconds is always set.
    If fresh=False and a previous coverage run exists, it is loaded instead of re-running.
    """
    data_file = os.path.abspath(os.path.join(data_dir, f"baseline_{label}.coverage"))
    json_file  = os.path.abspath(os.path.join(data_dir, f"baseline_{label}_coverage.json"))
    time_file  = os.path.abspath(os.path.join(data_dir, f"baseline_{label}_time.txt"))
    coveragerc = os.path.abspath(os.path.join(data_dir, f"baseline_{label}.coveragerc"))

    if not fresh and os.path.isfile(json_file) and os.path.isfile(time_file):
        with open(time_file, encoding="utf-8") as f:
            elapsed = float(f.read().strip())
        with open(json_file, encoding="utf-8") as f:
            cov_data = json.load(f)
        covered: dict[str, set[int]] = {}
        for filepath, file_data in cov_data.get("files", {}).items():
            covered[str(Path(filepath).resolve())] = set(file_data.get("executed_lines", []))
        acq_count = sum(1 for p in covered if "acquisition" in p)
        print(f"  Loaded cached baseline coverage for '{generator}' ({acq_count} acquisition module(s), {elapsed:.1f}s).")
        return covered, elapsed

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

    with open(time_file, "w", encoding="utf-8") as f:
        f.write(str(elapsed))

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
    return _is_covered_abs(str(mutation.module_path.resolve()), mutation.start_pos[0], covered)


def write_review_report(
    db: WorkDB,
    label: str,
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
    report_path = os.path.join(data_dir, f"survived_review_{label}.txt")
    not_equivalent_fingerprints = _load_fingerprints_json(
        os.path.join(data_dir, "not_equivalent_mutants.json")
    )
    total_count = 0
    unreviewed_count = 0
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
                total_count += 1
                if _mutation_fingerprint(mutation) not in not_equivalent_fingerprints:
                    unreviewed_count += 1
    reviewed_count = total_count - unreviewed_count
    detail = f", {reviewed_count} already reviewed" if reviewed_count else ""
    count_str = with_sgr(f"{unreviewed_count} survived mutant(s) to review", CLR_YELLOW_FG if unreviewed_count else CLR_GREEN_FG)
    print(f"Review report: {with_sgr(report_path, STYLE_DIM)} ({count_str}{detail})")


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

    def score_color(s: float) -> int:
        return CLR_GREEN_FG if s >= 0.8 else CLR_YELLOW_FG if s >= 0.6 else CLR_RED_FG

    print(f"Killed:       {with_sgr(f'{num_killed} ({pct(num_killed)})', CLR_GREEN_FG)}")
    if num_timeout:
        print(f"  Timeout:    {with_sgr(str(num_timeout), CLR_YELLOW_FG)}")
    survived_color = CLR_RED_FG if num_survived > 0 else CLR_GREEN_FG
    print(f"Survived:     {with_sgr(f'{num_survived} ({pct(num_survived)})', survived_color)}")
    if num_equivalent or num_uncovered:
        print(f"  {with_sgr('Equivalent:', STYLE_DIM)} {num_equivalent}")
        print(f"  {with_sgr('Uncovered: ', STYLE_DIM)} {num_uncovered}")
    print(f"{with_sgr('Incompetent:  ', STYLE_DIM)}{num_incompetent} ({pct(num_incompetent)})")
    print(f"{with_sgr('Untested:     ', STYLE_DIM)}{num_no_test} ({pct(num_no_test)})")
    abnormal_val = f"{num_abnormal} ({pct(num_abnormal)})"
    print(f"{with_sgr('Abnormal:     ', STYLE_DIM)}{with_sgr(abnormal_val, CLR_YELLOW_FG) if num_abnormal else abnormal_val}")
    print(f"{with_sgr('Skipped:      ', STYLE_DIM)}{num_skipped} ({pct(num_skipped)})")
    print(f"{with_sgr('Mutation score (covered):', STYLE_BOLD)}  {with_sgr(f'{covered_score:.1%}', score_color(covered_score))} ({num_killed}/{covered_denom})")
    print(f"{with_sgr('Mutation score (full):   ', STYLE_BOLD)}  {with_sgr(f'{full_score:.1%}', score_color(full_score))} ({num_killed}/{full_denom})")


def _reset_abnormal_and_timeout_to_pending(db: WorkDB, exclude_job_ids: set[str] | None = None) -> int:
    """Delete ABNORMAL, timed-out, and NO_TEST result rows so cr_execute retries them as pending.
    Returns the number of rows deleted.
    Job IDs in exclude_job_ids are left untouched.
    """
    from sqlalchemy import or_
    from cosmic_ray.work_db import WorkResultStorage as _WorkResultStorage

    with db._session_maker.begin() as session:  # type: ignore[attr-defined]
        query = (
            session.query(_WorkResultStorage)
            .where(or_(
                _WorkResultStorage.worker_outcome == WorkerOutcome.ABNORMAL,
                _WorkResultStorage.worker_outcome == WorkerOutcome.NO_TEST,
                (_WorkResultStorage.output == "timeout") & (_WorkResultStorage.test_outcome == TestOutcome.KILLED),
            ))
        )
        if exclude_job_ids:
            query = query.where(_WorkResultStorage.job_id.notin_(exclude_job_ids))
        return query.delete()


def _count_abnormal(db: WorkDB, exclude_job_ids: set[str] | None = None) -> int:
    """Count completed work items that would be reset by _reset_abnormal_and_timeout_to_pending."""
    return sum(
        1 for work_item, r in db.completed_work_items
        if (r.worker_outcome in (WorkerOutcome.ABNORMAL, WorkerOutcome.NO_TEST)
            or (r.output == "timeout" and r.test_outcome == TestOutcome.KILLED))
        and (exclude_job_ids is None or work_item.job_id not in exclude_job_ids)
    )


def _skip_uncovered_work_items(db: WorkDB, covered: dict[str, set[int]]) -> int:
    """Mark pending work items on uncovered lines as SURVIVED, returning the count."""
    if not covered:
        return 0
    to_skip = [
        wi.job_id
        for wi in db.pending_work_items
        if all(not _is_covered(m, covered) for m in wi.mutations)
    ]
    if not to_skip:
        return 0
    with db._session_maker.begin() as session:  # type: ignore[attr-defined]
        for job_id in to_skip:
            session.add(WorkResultStorage(
                job_id=job_id,
                worker_outcome=WorkerOutcome.NORMAL,
                test_outcome=TestOutcome.SURVIVED,
                output="Uncovered by baseline test suite",
                diff="Diff not available, as mutant was never generated.",
            ))
    return len(to_skip)


@dataclass
class _GeneratorSpec:
    generator: str
    generator_args: list[str]
    suite_size: int
    label_suffix: str | None = None

    def label(self) -> str:
        result = f"{self.generator}_{self.suite_size}"
        if self.label_suffix:
            result += f"_{self.label_suffix}"
        return result


def _generate_and_run_test_suite(
    generator_spec: _GeneratorSpec,
    fresh: bool,
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
    generator = generator_spec.generator
    generator_args = generator_spec.generator_args
    suite_size = generator_spec.suite_size
    label = generator_spec.label()

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

    cr_session_file = os.path.join(data_dir, f"cosmicray_{label}.sqlite")
    session_exists = os.path.isfile(cr_session_file)
    if session_exists and fresh:
        os.remove(cr_session_file)
        session_exists = False

    db_mode = WorkDB.Mode.open if session_exists else WorkDB.Mode.create
    start_time = time.monotonic()
    with work_db.use_db(cr_session_file, mode=db_mode) as db:  # type: ignore[attr-defined]
        preexisting_timeout_job_ids: set[str] = set()
        covered: dict[str, set[int]] = {}
        baseline_time: float = 0.0
        if session_exists:
            with contextlib.redirect_stdout(io.StringIO()):  # pragma_no_mutate is noisy!
                pragma_no_mutate.main((cr_session_file,))
            total = db.num_work_items
            preexisting_timeout_job_ids = {
                work_item.job_id
                for work_item, result in db.completed_work_items
                if result.output == "timeout"
            }
            abnormal_reset = _reset_abnormal_and_timeout_to_pending(db)
            pending = len(db.pending_work_items)
            reset_str = f", {with_sgr(f'{abnormal_reset} ABNORMAL/TIMEOUT reset', CLR_YELLOW_FG)}" if abnormal_reset else ""
            print(f"Resuming {with_sgr(generator, STYLE_BOLD)} ({suite_size} cases): {total - pending}/{total} done, {pending} pending{reset_str}.")
            covered, baseline_time = run_baseline_coverage(
                python_path, generator, label, generator_args, pytest_log_file, data_dir, fresh=False,
            )
        else:
            print(f"Running mutation analysis on {with_sgr(generator, STYLE_BOLD)} ({suite_size} cases)")
            print("Initialising WorkDB")
            cr_init(modules_to_mutate, work_db=db, operator_cfgs={})
            print(f"Created {db.num_work_items} work items.")
            print("Filtering...")
            operators_filter.main((cr_session_file, cr_config_file))
            with contextlib.redirect_stdout(io.StringIO()):  # pragma_no_mutate is noisy!
                pragma_no_mutate.main((cr_session_file,))
            print(f"Collecting baseline coverage for '{generator}'...")
            covered, baseline_time = run_baseline_coverage(
                python_path, generator, label, generator_args, pytest_log_file, data_dir, fresh,
            )
            num_coverage_skipped = _skip_uncovered_work_items(db, covered)
            if num_coverage_skipped:
                print(f"  Skipped {num_coverage_skipped} work item(s) on uncovered lines.")

        pending = len(db.pending_work_items)

        if pending == 0:
            print(f"  All work items already completed, skipping execution.")
        else:
            config["timeout"] = baseline_time * 2 + ACQUISITION_TIMEOUT
            print(f"  Baseline time: {baseline_time:.1f}s; timeout set to {config['timeout']:.1f}s")
            print(f"Executing {pending} work items...")
            report_end_event = Event()
            report_thread = Thread(target=_progress_reporter, args=(db, report_end_event), daemon=True)
            report_thread.start()
            try:
                cr_execute(work_db=db, config=config)
                _max_retries = 1
                for _attempt in range(1, _max_retries + 1):
                    abnormal_count = _count_abnormal(db, exclude_job_ids=preexisting_timeout_job_ids)
                    if abnormal_count == 0:
                        break
                    print(with_sgr(f"  Retrying {abnormal_count} ABNORMAL/TIMEOUT item(s) (attempt {_attempt}/{_max_retries})...", CLR_YELLOW_FG))
                    _reset_abnormal_and_timeout_to_pending(db, exclude_job_ids=preexisting_timeout_job_ids)
                    cr_execute(work_db=db, config=config)
                abnormal_count = _count_abnormal(db, exclude_job_ids=preexisting_timeout_job_ids)
                if abnormal_count > 0:
                    print(with_sgr(f"  {abnormal_count} ABNORMAL/TIMEOUT item(s) unresolved", CLR_YELLOW_FG))
            finally:
                report_end_event.set()
                report_thread.join(5)
                if report_thread.is_alive():
                    _logging.warning("Progress reporter didn't exit after all work items were executed.")

        print(with_sgr(f"Done with session: {cr_session_file}", STYLE_DIM))
        print_summary(db, equivalent_fingerprints, covered)
        write_review_report(db, label, data_dir, equivalent_fingerprints, covered)

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


def _wait_for_worker(port: int, timeout: float = 30.0, interval: float = 0.1) -> bool:
    """Poll until the worker on `port` accepts TCP connections. Returns False on timeout."""
    import socket
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=interval):
                return True
        except OSError:
            time.sleep(interval)
    return False


def _start_workers(
    worker_count: int,
    root_dir: str,
    data_dir: str,
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
        worker = multiprocessing.Process(target=_run_worker_sandboxed, args=(port, str(sandbox), data_dir))
        workers.append(worker)
        worker.start()
    for port in ports:
        if not _wait_for_worker(port):
            raise RuntimeError(f"Worker on port {port} did not become ready within 30s")
    urls = [f"http://localhost:{port}" for port in ports]
    return urls, workers, sandbox_dirs


def _stop_workers(
    workers: list[multiprocessing.Process],
    sandbox_dirs: list[Path],
) -> None:
    """Terminate all worker processes and remove their sandbox directories."""
    for worker in workers:
        try:
            if worker.is_alive():
                worker.terminate()
                worker.join(3)
            if worker.is_alive():
                worker.kill()
                worker.join(2)
        except Exception:
            pass
        try:
            worker.close()
        except Exception:
            pass
    for sandbox in sandbox_dirs:
        shutil.rmtree(str(sandbox), ignore_errors=True)


def _run_baseline_check(
    generator_spec: _GeneratorSpec,
    python_path: str,
    pytest_test_dir: str,
    root_dir: str,
    pytest_log_file: str,
    worker_urls: list[str],
    worker_count: int,
) -> None:
    """Run 2 rounds of worker_count unmodified passes through the worker pool.

    Round 1 is timed. The elapsed time*3 becomes the timeout for round 2. 
    Any failure indicates a prolbem with the worker infrastructure (sandboxing, port assignment, concurrent I/O).
    """
    generator = generator_spec.generator
    test_command = (
        f"\"{python_path}\" "
        f"-m pytest \"{pytest_test_dir}\" "
        f"--rootdir=\"{root_dir}\" "
        f"{' '.join(generator_spec.generator_args)} "
        f"--generator={generator} "
        f"--log-file=\"{pytest_log_file}\""
    )

    async def _run_round(timeout: float) -> list[dict]:
        available = list(worker_urls)
        in_flight: dict[asyncio.Task, str] = {}
        results: list[dict] = []

        async def _post(url: str) -> dict:
            params = {"mutations": [], "test_command": test_command, "timeout": timeout}
            try:
                async with aiohttp.request("POST", url, json=params) as resp:
                    return await resp.json()
            except Exception as exc:
                return {"worker_outcome": "abnormal", "test_outcome": None,
                        "output": str(exc), "diff": None}

        for _ in range(worker_count):
            while not available:
                done, _ = await asyncio.wait(in_flight.keys(), return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    available.append(in_flight.pop(task))
                    results.append(task.result())
            url = available.pop()
            task = asyncio.create_task(_post(url))
            in_flight[task] = url
        while in_flight:
            done, _ = await asyncio.wait(in_flight.keys(), return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                available.append(in_flight.pop(task))
                results.append(task.result())
        return results

    print(f"Running baseline verification for '{generator}' ({worker_count} workers, 2 rounds)...")

    print(f"  Round 1/2: {worker_count} passes (calibrating timeout)...")
    t0 = time.monotonic()
    round_1_results = asyncio.run(_run_round(3600.0))
    round_1_elapsed = time.monotonic() - t0
    calibrated_timeout = round_1_elapsed * 3
    print(f"  Round 1 elapsed: {round_1_elapsed:.1f}s. Timeout for round 2: {calibrated_timeout:.1f}s")

    print(f"  Round 2/2: {worker_count} passes...")
    all_results = round_1_results + asyncio.run(_run_round(calibrated_timeout))

    num_runs = 2 * worker_count
    passed = sum(1 for r in all_results if r.get("test_outcome") == "survived")
    failed = num_runs - passed
    if failed == 0:
        print(with_sgr(f"  All {num_runs} baseline passes passed.", CLR_GREEN_FG))
    else:
        print(with_sgr(f"  {failed}/{num_runs} baseline passes FAILED:", CLR_RED_FG))
        for i, r in enumerate(all_results):
            if r.get("test_outcome") != "survived":
                out = (r.get("output") or "").strip().splitlines()
                relevant = [ln for ln in out if "FAILED" in ln or "Error" in ln or "assert" in ln.lower()]
                relevant = relevant or (out[-5:] if out else ["(no output)"])
                print(f"    Run {i + 1}: {r.get('worker_outcome')}")
                for ln in relevant:
                    print(f"      {ln}")


_DIFF_LINE_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@")
def _check_review_consistency(data_dir: str, root_dir: str, labels: list[str]) -> list[str]:
    """Verify that diffs in existing review files still match the current source files.
    Returns a list of discrepancy descriptions - empty means all consistent.
    """
    from gemeaspy.tests.review_mutants import parse_review_file

    review_files = [
        p for label in labels
        if (p := Path(data_dir) / f"survived_review_{label}.txt").is_file()
    ]
    if not review_files:
        return []

    discrepancies: list[str] = []

    for review_path in review_files:
        for entry in parse_review_file(review_path):
            if not entry.diff:
                continue

            diff_lines = entry.diff.splitlines()

            source_rel: str | None = None
            for line in diff_lines:
                if line.startswith("--- a"):
                    source_rel = line[5:]
                    break
            if source_rel is None:
                continue

            source_path = Path(root_dir) / source_rel.replace("\\", "/")
            if not source_path.is_file():
                discrepancies.append(
                    f"{review_path.name}: source file not found: {source_rel}"
                )
                continue

            source_lines = source_path.read_text(encoding="utf-8").splitlines()
            label = (
                f"{review_path.name}: "
                f"{entry.module_path} {entry.operator_name} #{entry.occurrence}"
            )

            diff_start: int | None = None
            src_offset = 0

            for diff_line in diff_lines:
                m = _DIFF_LINE_RE.match(diff_line)
                if m:
                    diff_start = int(m.group(1))
                    src_offset = 0
                    continue
                if diff_start is None:
                    continue
                if diff_line.startswith("+") and not diff_line.startswith("+++"):
                    continue  # added line, not in the original source
                if diff_line.startswith("\\"):
                    continue  # "\ No newline at end of file" marker
                # only removed lines are compared against the current source
                is_removed = diff_line.startswith("-") and not diff_line.startswith("---")
                if is_removed:
                    expected = diff_line[1:].rstrip()
                    line_idx = diff_start + src_offset - 1  # convert to 0-based
                    if line_idx >= len(source_lines):
                        discrepancies.append(
                            f"{label}: line {line_idx + 1} is beyond end of file "
                            f"(file has {len(source_lines)} lines)"
                        )
                    elif source_lines[line_idx].rstrip() != expected:
                        discrepancies.append(
                            f"{label}: line {line_idx + 1}:\n"
                            f"    expected: {expected!r}\n"
                            f"    got:      {source_lines[line_idx]!r}"
                        )
                src_offset += 1

    return discrepancies


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
    parser.add_argument("--workers", type=int, default=None, metavar="N", help="Number of HTTP workers (default: cpu count - 1)")
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        metavar="N",
        help="Seed for random test suite (default: 0)",
    )
    parser.add_argument("--fresh", action="store_true", help="Delete any existing session file and start a fresh mutation run (default: resume from existing session)")
    parser.add_argument("--verify-baseline", dest="baseline", action="store_true", help="Run baseline verification instead of mutation analysis: sends 2 * workers unmodified test passes through the worker pool")
    args = parser.parse_args()

    if args.size is not None:
        generators_to_run = [
            _GeneratorSpec(
                generator="random",
                generator_args=[f"--size={args.size}", f"--seed={args.seed}"],
                suite_size=args.size,
                label_suffix=f"s{args.seed}",
            )
        ]
        if args.only != "random":
            print(f"Searching for smallest acts suite above size {args.size}...")
            found = _find_min_acts_strength_above(PYTHON_PATH, PYTEST_TEST_DIR, ROOT_DIR, args.size)
            if found is not None:
                strength, acts_size = found
                print(f"  Found: strength={strength} yields {acts_size} test cases.")
                generators_to_run.append(
                    _GeneratorSpec("acts", [f"--strength={strength}"], acts_size)
                )
            else:
                print(f"  No acts suite found above size {args.size} (tried strength 1-6); skipping acts.")
        if args.only == "acts":
            generators_to_run = [g for g in generators_to_run if g.generator == "acts"]
    else:
        acts_size = _acts_suite_size(PYTHON_PATH, PYTEST_TEST_DIR, ROOT_DIR, args.strength)
        print(f"Acts suite at strength={args.strength}: {acts_size} test cases.")
        generators_to_run = [
            _GeneratorSpec("acts", [f"--strength={args.strength}"], acts_size),
            _GeneratorSpec(
                generator="random",
                generator_args=[f"--size={acts_size}", f"--seed={args.seed}"],
                suite_size=acts_size,
                label_suffix=f"s{args.seed}",
            ),
        ]
        if args.only is not None:
            generators_to_run = [
                g for g in generators_to_run if g.generator == args.only
            ]

    discrepancies = _check_review_consistency(DATA_DIR, ROOT_DIR, [g.label() for g in generators_to_run])
    if discrepancies:
        print(with_sgr("Warning: review file(s) are stale - source has changed since they were generated:", CLR_YELLOW_FG))
        for msg in discrepancies:
            print(f"  {msg}")
        print("Delete or regenerate the stale review file(s) before continuing.")
        sys.exit(1)

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

    worker_count: int | None = 1
    if args.workers and isinstance(args.workers, int):
        worker_count = args.workers
    elif (num_cpus := psutil.cpu_count(logical=False)) != None:
        worker_count = max(1, num_cpus - 1)
    else:
        print("Failed to determine number of worker threads; please set manually with --workers.")
        return
        
    PORT_BASE = 55430
    if "distributor" not in config:
        config["distributor"] = {}
    if "http" not in config["distributor"]:
        config["distributor"]["http"] = {}
    worker_urls, workers, sandbox_dirs = _start_workers(worker_count, ROOT_DIR, DATA_DIR, PORT_BASE)
    config["distributor"]["http"]["worker-urls"] = worker_urls

    os.makedirs(DATA_DIR, exist_ok=True)

    if not args.baseline:
        equivalent_fingerprints = load_equivalent_fingerprints(DATA_DIR)
        if equivalent_fingerprints:
            print(f"Loaded {len(equivalent_fingerprints)} equivalent mutant fingerprint(s).")

    baseline_t0 = time.monotonic()
    try:
        for generator in generators_to_run:
            if args.baseline:
                _run_baseline_check(
                    generator,
                    PYTHON_PATH,
                    PYTEST_TEST_DIR,
                    ROOT_DIR,
                    PYTEST_LOG_FILE,
                    worker_urls,
                    worker_count,
                )
            else:
                _generate_and_run_test_suite(
                    generator,
                    args.fresh,
                    config,
                    modules_to_mutate,
                    equivalent_fingerprints,
                    PYTHON_PATH,
                    PYTEST_LOG_FILE,
                    DATA_DIR,
                    CR_CONFIG_FILE,
                    PYTEST_TEST_DIR,
                    ROOT_DIR,
                )
    except KeyboardInterrupt:
        print(with_sgr("\nInterrupted.", CLR_YELLOW_FG))
        return
    finally:
        _stop_workers(workers, sandbox_dirs)
        _merge_incompetent_caches()

    if args.baseline:
        print(f"Total verification time: {time.monotonic() - baseline_t0:.1f}s")
        return

    equiv_file = os.path.join(DATA_DIR, "equivalent_mutants.json")
    print()
    print("Output files:")
    for generator in generators_to_run:
        label = generator.label()
        print(f"  [{label}] session:       {os.path.join(DATA_DIR, f'cosmicray_{label}.sqlite')}")
        print(f"  [{label}] review report: {os.path.join(DATA_DIR, f'survived_review_{label}.txt')}")

    reviewed = (
        _load_fingerprints_json(os.path.join(DATA_DIR, "equivalent_mutants.json"))
        | _load_fingerprints_json(os.path.join(DATA_DIR, "not_equivalent_mutants.json"))
    )
    report_fingerprints: set[tuple[str, str, int]] = set()
    for generator in generators_to_run:
        report_fingerprints |= _fingerprints_from_review_report(
            os.path.join(DATA_DIR, f"survived_review_{generator.label()}.txt")
        )
    if report_fingerprints.issubset(reviewed):
        return

    print()
    print(with_sgr("Testing complete. Next steps for manual review:", STYLE_BOLD))
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
    print('     This can be done in a more convenient way by running review_mutants.py')
    print("     Equivalent mutants are excluded from the mutation score on the next run.")
    print()
    print("  4. Re-run with the same generators to see the updated mutation score.")


if __name__ == "__main__":
    main()
