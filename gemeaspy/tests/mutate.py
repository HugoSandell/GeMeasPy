"""CLI script to perform testing and mutation analysis."""
import os
import sys
import time
from pathlib import Path
from typing import Any

from cosmic_ray import work_db
import cosmic_ray.config
from cosmic_ray.commands.execute import execute as cr_execute
from cosmic_ray.commands.init import init as cr_init
from cosmic_ray.config import ConfigDict
from cosmic_ray.work_db import WorkDB
from cosmic_ray.tools.filters import operators_filter

import gemeaspy

def main():
    ROOTPKG_DIR = os.path.split(gemeaspy.__file__)[0]
    ROOT_DIR = os.path.split(ROOTPKG_DIR)[0]
    DATA_DIR = os.path.join(ROOT_DIR, "test_data")
    CR_CONFIG_FILE = os.path.join(ROOT_DIR, "cosmic-ray.toml")
    PYTEST_LOG_FILE = os.path.join(DATA_DIR, "pytest.log")
    
    modules_to_mutate: list[Path] = []
    for dirpath, _, filenames in os.walk("./gemeaspy/acquisition"):
        for filename in filenames:
            if filename.endswith(".py") and filename not in ("__init__.py", "__main__.py"):
                modules_to_mutate.append(Path(dirpath, filename))

    # Getting the absolute path fixes an issue where subprocess.run in cosmic-ray 
    # executes the wrong python executable 
    PYTHON_PATH = sys.executable
    
    VALID_GENERATORS = {"random": "--size=200", "acts": "--strength=2"}
    requested_generators = [g.strip().lower() for g in sys.argv[1:]]
    
    invalid_generators = [g for g in requested_generators if g not in VALID_GENERATORS]
    if len(invalid_generators) > 0:
        print(f"Invalid generator{"s" if len(invalid_generators) > 1 else ""}: {", ".join(invalid_generators)}", file=sys.stderr)
        sys.exit(1)

    config: ConfigDict = cosmic_ray.config.load_config(CR_CONFIG_FILE)
    config["module-path"] = ["gemeaspy/acquisition"]
    config["timeout"] = 120.0
    config["excluded-modules"] = ["gemeaspy/tests"]
    config["distributor"]["name"] = "local"
    os.makedirs(DATA_DIR, exist_ok=True)

    operator_cfgs: dict[str, Any] = {}

    for generator in requested_generators:
        print(f"Running mutation analysis on test case generator '{generator}'")
        
        config["test-command"] = f"\"{PYTHON_PATH}\" -m coverage run --data-file={generator}.coverage --branch -m pytest {VALID_GENERATORS[generator]} --generator={generator} " \
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
            cr_execute(work_db=db, config=config)
            print(f"Done with session: {cr_session_file}")
    
        execution_time = time.monotonic() - start_time
        print(f"'{generator}' done in {execution_time} seconds. Session is written to {cr_session_file}.")
    print("Testing complete!")


if __name__ == "__main__":
    main()