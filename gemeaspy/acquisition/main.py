import os
import sys
import traceback

import gemeaspy.acquisition.error as error
from gemeaspy.acquisition.error import (
    InvalidLocalDirectoryError,
)
from gemeaspy.acquisition.instruments import Terrameter
from gemeaspy.acquisition.logger import logger
from gemeaspy.acquisition.utilities import read_monitoring_tasks
from gemeaspy.settings import config


def run_task_file(task_file) -> None:
    # Make sure we can access the local data path
    is_local_data_directory_ok = True
    if not os.path.exists(config.LOCAL_PATH_TO_DATA):
        try:
            logger.debug(f"Creating directory {config.LOCAL_PATH_TO_DATA!r}")
            os.makedirs(config.LOCAL_PATH_TO_DATA)
        except Exception as e:
            logger.debug(f"Caught exception {e}")
            is_local_data_directory_ok = False
    elif not os.path.isdir(config.LOCAL_PATH_TO_DATA):
        logger.warning(f"{config.LOCAL_PATH_TO_DATA!r} exists, but is not a directory!")
        is_local_data_directory_ok = False
    if not is_local_data_directory_ok:
        raise InvalidLocalDirectoryError("Failed to create directory.", config.LOCAL_PATH_TO_DATA)
    logger.debug(f"Ensured local data directory {config.LOCAL_PATH_TO_DATA!r} exists")   
    
	# read connection and measurement settings
    ls = Terrameter()
    ls.connect()
    ls.check_input(read_monitoring_tasks(task_file))
    ls.start_monitoring(task_file)
    ls.disconnect()

def run_acquisition(argv: list[str]) -> int:
    nargs = len(argv)
    logger.info(f"\n\nRunning acquisition with argument{"s" if nargs>1 else ""}: {" ".join(argv[1:])}")
    if nargs == 1:
        task_file = None
        print(f"Error: No task file given")
        logger.error(f"Acquisition was run with no input")
        return 2
    try: 
        task_files = argv[1:]
        for task_file in task_files:
            run_task_file(task_file)
    except Exception as e:
        return error.handle_exception(e)
    return 0

def cli_main():
    # Read environment variables
    for _var in config.__dict__:
        if not hasattr(config, _var) or _var not in os.environ:
            continue
        try:
            setattr(config, _var, type(_var)(os.environ[_var]))
        except Exception:
            print(f"Ignoring invalid environment variable {_var}='{os.environ[_var]}'")
    try:
        exit_code = run_acquisition(sys.argv)
        sys.exit(exit_code)
    except Exception as e:
        print(f"Error: An unexpected error occured. Check logs for more information.")
        logger.error(f"Unhandled exception.", exc_info=True)
        if "DEBUG" in os.environ:
            traceback.print_exception(e, file=sys.stderr)
        sys.exit(1)