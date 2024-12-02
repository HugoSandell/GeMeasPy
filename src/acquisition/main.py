import sys

from acquisition.instruments import Terrameter
from acquisition.utilities import read_monitoring_tasks
from settings.config import REMOTE_BACKUP


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
	elif nargs == 2:
		task_file = sys.argv[1]
	else:
		# TODO: In case we have more than one task files
		task_file = sys.argv[1:]
	run(task_file)
