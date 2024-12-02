import sys

from acquisition import utilities
from acquisition import instruments



def run(task_file: str) -> None:
    # read connection and measurement settings
    ls = instruments.Terrameter()
    ls.connect()
    task_list = utilities.read_monitoring_tasks(task_file)
    ls.check_input_report(task_list)
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
	