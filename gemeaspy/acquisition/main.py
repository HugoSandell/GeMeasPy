import os
import sys
import traceback

from paramiko import ChannelException

from gemeaspy.acquisition.error import (
    ConfigFileError,
    InvalidLocalDirectory,
    MissingFileError,
    SSHConnectionError,
    TaskFileIOError,
    TaskFileParseError,
    TransferError,
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
        raise InvalidLocalDirectory("Failed to create directory.", config.LOCAL_PATH_TO_DATA)
    logger.debug(f"Ensured local data directory {config.LOCAL_PATH_TO_DATA!r} exists")   
    
	# read connection and measurement settings
    ls = Terrameter()
    ls.connect()
    ls.check_input(read_monitoring_tasks(task_file))
    ls.start_monitoring(task_file)
    ls.disconnect()

def run_acquisition(argv: list[str]) -> int:
    verbose = "DEBUG" in os.environ
    
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
    # NOTE: All fatal exceptions shall start with 'Error:'
    except ChannelException as e:
        print("Error: Failed to create SSH channel connection to Terrameter!")
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
    except TaskFileIOError as e:
        print(f"Error: Failed to read task file {e.file!r}!")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"TaskFileIOError - Failed to read {e.file!r}", exc_info=True)
        return 7
    except TaskFileParseError as e:
        if e.file is None:
            print(f"Error: Failed to parse task file: {e.msg}")
        else:
            print(f"Error: Failed to parse task file {e.file!r}: {e.msg}")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"TaskFileParseError - {e.msg}", exc_info=True)
        return 8
    except MissingFileError as e:
        print(f"Error: Task file references a non-existent file - {e.msg} {e.file!r}")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"MissingFileError - {e.msg} {e.file!r}", exc_info=True)
        return 9
    except InvalidLocalDirectory as e:
        print(f"Error: Local data directory {e.dir!r} could not be used - {e.msg}")
        if verbose:
            traceback.print_exception(e, file=sys.stderr)
        logger.error(f"InvalidLocalDirectory - {e.msg} {e.dir!r}", exc_info=True)
        return 10
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