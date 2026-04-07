import logging
import os
from pathlib import Path
import sys
import traceback

from paramiko import ChannelException

from gemeaspy.settings import config
from gemeaspy.acquisition.error import ConfigFileError, SSHConnectionError, TransferError
from gemeaspy.acquisition.instruments import Terrameter
from gemeaspy.acquisition.utilities import read_monitoring_tasks

logger: logging.Logger = logging.root

def setup_logger(log_path: str) -> logging.Logger:
    logging.getLogger("paramiko").setLevel(logging.ERROR)
    os.makedirs(Path(log_path).parent, exist_ok=True)
    logger = logging.Logger("acquisition")
    logger.addHandler(logging.FileHandler(log_path))
    return logger

def run_task_file(task_file) -> None:
	# read connection and measurement settings
    ls = Terrameter()
    ls.connect()
    if ls.check_input(read_monitoring_tasks(task_file)) is False:
        print('Error in the task file: possible spreads/protocols missing!')
    ls.start_monitoring(task_file)
    ls.disconnect()

def run_acquisition(argv: list[str]) -> int:
    logger: logging.Logger = setup_logger("log/acquisition.log")
    verbose = "DEBUG" in os.environ
    
    nargs = len(argv)
    if nargs == 1:
        task_file = None
        print(f"Error: No task file given")
        logger.error(f"Acquisition was run with no input")
        return 2
    try: 
        if nargs == 2:
            task_file = argv[1]
            run_task_file(task_file)
        else:
            task_files = argv[1:]
            for task_file in task_files:
                run_task_file(task_file)
    # NOTE: All fatal exceptions shall start with 'Error:'
    except ChannelException as e:
        print("Error: Failed to create SSH shell channel to Terrameter!")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"ChannelException - [{e.code}] {e.text}", exc_info=True)
        return 3
    except ConfigFileError as e:
        print(f"Error: {e.msg} ({e.file})")
        logger.error(f"ConfigFileError - [{e.file}] {e.msg}", exc_info=True)
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        return 4
    except TransferError as e:
        print(f"Error: Project transfer failed - {e.msg} ({e.file})")
        logger.error(f"TransferError - [{e.file}] {e.msg}", exc_info=True)
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        return 5
    except SSHConnectionError as e:
        print(f"Error: A connection error occured - {e.msg}")
        logger.error(f"SSHConnectionError - [{e.params}] {e.msg}", exc_info=True)
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        return 6
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