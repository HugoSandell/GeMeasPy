import sys

from acquisition.instruments import Terrameter
from acquisition.utilities import read_monitoring_tasks


def run(task_file) -> None:
	# read connection and measurement settings
    ls = Terrameter()
    ls.connect()
    if ls.check_input(read_monitoring_tasks(task_file)) is False:
        print('Error in the task file: possible spreads/protocols missing!')
    ls.start_monitoring(task_file)
    ls.disconnect()


if __name__ == "__main__":
	nargs = len(sys.argv)
	if nargs == 1:
		task_file = None
		raise Exception("No task file provided")
	elif nargs == 2:
		task_file = sys.argv[1]
		run(task_file)
	else:
		task_files = sys.argv[1:]
		for task_file in task_files:
			run(task_file)
