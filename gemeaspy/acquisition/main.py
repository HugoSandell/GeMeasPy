import logging
import sys

from paramiko import ChannelException

from gemeaspy.acquisition.error import ConfigFileError
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

def run_acquisition(argv: list[str]):
    logging.getLogger("paramiko").setLevel(logging.ERROR)
    nargs = len(argv)
    if nargs == 1:
        task_file = None
        raise SystemExit("No task file provided")
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
        logging.info(f"ChannelException - [{e.code}] {e.text}")
        return False
    except ConfigFileError as e:
        print(f"Error: {e.msg} ({e.file})")
        logging.info(f"ConfigFileError - [{e.file}] {e.msg}")

if __name__ == "__main__":
    run_acquisition(sys.argv)
