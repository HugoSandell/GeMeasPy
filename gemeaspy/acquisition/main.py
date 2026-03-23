import logging
import os
import sys
import traceback

from paramiko import ChannelException

from gemeaspy.acquisition.error import ConfigFileError, TransferError
from gemeaspy.acquisition.instruments import Terrameter
from gemeaspy.acquisition.utilities import read_monitoring_tasks


def run_task_file(task_file) -> None:
	# read connection and measurement settings
    ls = Terrameter()
    ls.connect()
    if ls.check_input(read_monitoring_tasks(task_file)) is False:
        print('Error in the task file: possible spreads/protocols missing!')
    ls.start_monitoring(task_file)
    ls.disconnect()

def run_acquisition(argv: list[str]) -> int:
    logging.getLogger("paramiko").setLevel(logging.ERROR)
    
    verbose = "DEBUG" in os.environ
    
    nargs = len(argv)
    if nargs == 1:
        task_file = None
        print(f"Error: No task file given")
        logging.error(f"Acquisition was run with no input")
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
            print(traceback.format_exc(), sys.stderr)
        logging.error(f"ChannelException - [{e.code}] {e.text}", exc_info=True)
        return 3
    except ConfigFileError as e:
        print(f"Error: {e.msg} ({e.file})")
        logging.error(f"ConfigFileError - [{e.file}] {e.msg}", exc_info=True)
        if verbose:
            print(traceback.format_exc(), sys.stderr)
        return 4
    except TransferError as e:
        print(f"Error: Project transfer failed - {e.msg} ({e.file})")
        logging.error(f"TransferError - [{e.file}] {e.msg}", exc_info=True)
        if verbose:
            print(traceback.format_exc(), sys.stderr)
        return 5
    except Exception as e:
        print(f"Error: An unexpected error occured. Check logs for more information.")
        logging.error(f"{str(type(e))} - {e}", exc_info=True)
        if verbose:
            print(traceback.format_exc(), sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    exit_code = run_acquisition(sys.argv)
    exit(exit_code)
