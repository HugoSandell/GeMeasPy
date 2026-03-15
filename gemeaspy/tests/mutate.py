import sys
import os
import typing
from time import time

import gemeaspy
import cosmic_ray.config
import cosmic_ray.work_db

from cosmic_ray.commands.execute import execute as cr_execute
from cosmic_ray.config import ConfigDict
from cosmic_ray.work_db import WorkDB
from cosmic_ray.work_item import WorkItem

def main():
    ROOTPKG_DIR = os.path.split(gemeaspy.__file__)[0]
    ROOT_DIR = os.path.split(ROOTPKG_DIR)[0]
    DATA_DIR = os.path.join(ROOT_DIR, "test_data")
    CR_CONFIG_FILE = os.path.join(ROOT_DIR, "cosmic-ray.toml")
    PYTEST_LOG_FILE = os.path.join(DATA_DIR, "pytest.log")

    # Getting the absolute path fixes an issue where subprocess.run in cosmic-ray 
    # executes the wrong python executable 
    PYTHON_PATH = sys.executable
    
    VALID_GENERATORS = {"random": "-N=200", "acts": "-T=2"}
    requested_generators = [g.strip().lower() for g in sys.argv[1:]]
    
    invalid_generators = [g for g in requested_generators if g not in VALID_GENERATORS]
    if len(invalid_generators) > 0:
        print(f"Invalid generator{"s" if len(invalid_generators) > 1 else ""}: {", ".join(invalid_generators)}", file=sys.stderr)
        exit(1)

    config: ConfigDict = cosmic_ray.config.load_config(CR_CONFIG_FILE)
    config["module-path"] = ["gemeaspy/acquisition"]
    config["timeout"] = 120.0
    config["excluded-modules"] = ["gemeaspy/tests"]
    config["distributor"]["name"] = "local"

    for generator in requested_generators:
        print(f"Running mutation analysis on test case generator '{generator}'")
        
        config["test-command"] = f"\"{PYTHON_PATH}\" -m pytest {VALID_GENERATORS[generator]} --generator={generator} " \
            f"--log-file=\"{PYTEST_LOG_FILE}\""
        
        cr_session_file = os.path.join(DATA_DIR, f"cosmicray_{generator}.sqlite")
        # Reinitialise
        if os.path.isfile(cr_session_file):
            os.remove(cr_session_file)
        start_time = time() 
        with cosmic_ray.work_db.use_db(cr_session_file, mode=WorkDB.Mode.create) as db:
            work_baseline = WorkItem("baseline", [])
            db.add_work_item(work_baseline)
            cr_execute(work_db=db, config=config)
        execution_time = time() - start_time
        print(f"'{generator}' done in {execution_time} seconds. Session is written to {cr_session_file}.")
    print("Testing complete!")


if __name__ == "__main__":
    main()