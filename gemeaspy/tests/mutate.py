import sys
import os

import gemeaspy
import cosmic_ray.config
import cosmic_ray.work_db
from cosmic_ray.distribution.local import LocalDistributor as CRLocalDistributor
from cosmic_ray.commands.execute import execute as cr_execute
from cosmic_ray.config import ConfigDict
from cosmic_ray.work_db import WorkDB
from cosmic_ray.work_item import WorkItem

def main():
    ROOTPKG_DIR = os.path.split(gemeaspy.__file__)[0]
    TEST_DIR = os.path.join(ROOTPKG_DIR, "tests")
    ROOT_DIR = os.path.split(ROOTPKG_DIR)[0]
    DATA_DIR = os.path.join(ROOT_DIR, "test_data")
    PYTEST_CONFIG_FILE = os.path.join(ROOT_DIR, "pytest.toml")
    CR_CONFIG_FILE = os.path.join(ROOT_DIR, "cosmic-ray.toml")
    CR_SESSION_FILE = os.path.join(DATA_DIR, "cosmicray_acts.sqlite")
    PYTEST_LOG_FILE = os.path.join(DATA_DIR, "pytest.log")

    # Getting the absolute path fixes an issue where subprocess.run in cosmic-ray 
    # executes the wrong python executable 
    PYTHON_PATH = sys.executable

    config: ConfigDict = cosmic_ray.config.load_config(CR_CONFIG_FILE)
    config["module-path"] = ["gemeaspy/acquisition"]
    config["timeout"] = 120.0
    config["excluded-modules"] = ["gemeaspy/tests"]
    config["distributor"]["name"] = "local"

    config["test-command"] = f"\"{PYTHON_PATH}\" -m pytest -T=3 --generator=acts " \
        f"--log-file=\"{PYTEST_LOG_FILE}\" -c \"{PYTEST_CONFIG_FILE}\" \"{TEST_DIR}\""

    # Reinitialise
    if os.path.isfile(CR_SESSION_FILE):
        os.remove(CR_SESSION_FILE)
    with cosmic_ray.work_db.use_db(CR_SESSION_FILE, mode=WorkDB.Mode.create) as db:
        work_baseline = WorkItem("baseline", [])
        db.add_work_item(work_baseline)
        cr_execute(work_db=db, config=config)


if __name__ == "__main__":
    main()