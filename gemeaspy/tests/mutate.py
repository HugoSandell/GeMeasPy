"""CLI script to perform testing and mutation analysis."""
import multiprocessing
from multiprocessing.connection import PipeConnection
import os
import sys
import time
from pathlib import Path
from typing import Any, TextIO
from threading import Thread, Event

from cosmic_ray import work_db
import cosmic_ray.config
from cosmic_ray.commands.execute import execute as cr_execute
from cosmic_ray.commands.init import init as cr_init
from cosmic_ray.config import ConfigDict
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkerOutcome
from cosmic_ray.tools.filters import operators_filter
from cosmic_ray.distribution.http import run_worker

import gemeaspy
from gemeaspy.tests import _logging

def _reporter(db: WorkDB, end_event: Event):
    """Repeatedly report status until all work is done"""
    num_items = len(db.pending_work_items)
    while len(db.pending_work_items) > 0 and not end_event.is_set():
        time.sleep(1.0)
        print("\r" + (" " * os.get_terminal_size().columns) + f"\rRunning work item {num_items - len(db.pending_work_items)}/{num_items}", end="")
    print()

def print_summary(db: WorkDB):
    """Summarise and print the results of a WorkDB"""
    
    results = list(db.completed_work_items)
    num_killed      = sum(1 for _, r in results if r.test_outcome == TestOutcome.KILLED)
    num_survived    = sum(1 for _, r in results if r.test_outcome == TestOutcome.SURVIVED)
    num_incompetent = sum(1 for _, r in results if r.test_outcome == TestOutcome.INCOMPETENT)
    # worker-level issues with no test_outcome
    num_no_test  = sum(1 for _, r in results if r.worker_outcome == WorkerOutcome.NO_TEST)
    num_abnormal = sum(1 for _, r in results if r.worker_outcome == WorkerOutcome.ABNORMAL)
    num_skipped  = sum(1 for _, r in results if r.worker_outcome == WorkerOutcome.SKIPPED)
    # Equivalent mutants
    num_equivalent = 0 # TODO: Count equivalent mutants!

    denominator = num_killed + num_survived - num_equivalent  # excludes incompetent, no_test, abnormal, skipped, and equivalent
    mutation_score = num_killed / denominator if denominator > 0 else 0.0

    print(f"Killed: {num_killed} ({num_killed/len(results):%})")
    print(f"Survived: {num_survived} ({num_survived/len(results):%})")
    print(f"Incompetent: {num_incompetent} ({num_incompetent/len(results):%})")
    print(f"Equivalent: {num_equivalent} ({num_equivalent/len(results):%})")
    print(f"Untested: {num_no_test} ({num_no_test/len(results):%})")
    print(f"Abnormal: {num_abnormal} ({num_abnormal/len(results):%})")
    print(f"Skipped: {num_skipped} ({num_skipped/len(results):%})")
    print(f"Mutation score: {mutation_score:.1f}")

def main():
    ROOTPKG_DIR = os.path.split(gemeaspy.__file__)[0]
    ROOT_DIR = os.path.split(ROOTPKG_DIR)[0]
    DATA_DIR = os.path.join(ROOT_DIR, "test_data")
    CR_CONFIG_FILE = os.path.join(ROOT_DIR, "cosmic-ray.toml")
    PYTEST_LOG_FILE = os.path.join(DATA_DIR, "pytest.log")
    # Getting the absolute path fixes an issue where subprocess.run in cosmic-ray 
    # executes the wrong python executable 
    PYTHON_PATH = sys.executable
    DEFAULT_GENERATOR_ARGUMENTS = {"random": "--size=5", "acts": "--strength=1"}
    
    modules_to_mutate: list[Path] = []
    for dirpath, _, filenames in os.walk("./gemeaspy/acquisition"):
        for filename in filenames:
            if filename.endswith(".py") and filename not in ("__init__.py", "__main__.py"):
                modules_to_mutate.append(Path(dirpath, filename))

    requested_generators = [g.strip().lower() for g in sys.argv[1:]]
    
    invalid_generators = [g for g in requested_generators if g not in DEFAULT_GENERATOR_ARGUMENTS]
    if len(invalid_generators) > 0:
        print(f"Invalid generator{"s" if len(invalid_generators) > 1 else ""}: {", ".join(invalid_generators)}", file=sys.stderr)
        sys.exit(1)
    
    config: ConfigDict = cosmic_ray.config.load_config(CR_CONFIG_FILE)
    config["module-path"] = ["gemeaspy/acquisition"]
    config["timeout"] = 120.0
    config["excluded-modules"] = ["gemeaspy/acquisition/subvision_relay.py"]
    config["distributor"]["name"] = "http"
    
    worker_count = multiprocessing.cpu_count()
    worker_ports = [9190 + i for i in range(worker_count)]
    config["distributor"]["http"]["worker-urls"] = [f"http://localhost:{port}" for port in worker_ports]
    workers: list[multiprocessing.Process] = []
    for port in worker_ports:
        worker = multiprocessing.Process(target=run_worker, args=(port,))
        workers.append(worker)
        worker.start()
    
    os.makedirs(DATA_DIR, exist_ok=True)

    operator_cfgs: dict[str, Any] = {}

    for generator in requested_generators:
        print(f"Running mutation analysis on test case generator '{generator}'")
        
        #config["test-command"] = f"\"{PYTHON_PATH}\" -m coverage run --data-file={generator}.coverage --branch -m pytest {DEFAULT_GENERATOR_ARGUMENTS[generator]} --generator={generator} " \
        #    f"--log-file=\"{PYTEST_LOG_FILE}\""
        config["test-command"] = f"\"{PYTHON_PATH}\" " \
            "-m pytest {DEFAULT_GENERATOR_ARGUMENTS[generator]} " \
            "--generator={generator} " \
            f"--log-file=\"{PYTEST_LOG_FILE}\""

        cr_session_file = os.path.join(DATA_DIR, f"cosmicray_{generator}.sqlite")

        # Reinitialise
        if os.path.isfile(cr_session_file):
            os.remove(cr_session_file)
        start_time = time.monotonic()
        
        with work_db.use_db(cr_session_file, mode=WorkDB.Mode.create) as db:
            print(f"Initialising WorkDB")
            cr_init(modules_to_mutate, work_db=db, operator_cfgs=operator_cfgs)
            print(f"Created {db.num_work_items} work items.")
            print(f"Filtering...")
            operators_filter.main((cr_session_file, CR_CONFIG_FILE))
            print(f"Executing {len(db.pending_work_items)} work items...")
            report_end_event = Event()
            report_process = Thread(target=_reporter, args=(db, report_end_event), daemon=True)
            report_process.start()
            cr_execute(work_db=db, config=config)
            report_end_event.set()
            report_process.join(5)
            if report_process.is_alive():
                _logging.warning("Progress reporter didn't exit after all work items were executed.")
            
            print(f"Done with session: {cr_session_file}")
            print_summary(db)
    
        execution_time = time.monotonic() - start_time
        print(f"'{generator}' done in {execution_time} seconds. Session is written to {cr_session_file}.")
    
    try:
        for worker in workers:
            worker.terminate()
            worker.join(5)
            worker.close()
    except multiprocessing.TimeoutError:
        print("Worker processes are not closing normally")
    print("Testing complete!")


if __name__ == "__main__":
    main()