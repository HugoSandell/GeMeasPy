import sys

from acquisition import utilities
from acquisition import instruments



def run(task_file):
    # read connection and measurement settings
    connection_parameters = utilities.read_connection_parameters()
    ls = instruments.Terrameter(connection_parameters)
    ls.connect()
    task_list = utilities.read_monitoring_tasks_updated(task_file)
    ls.check_input_report(task_list)
    ls.disconnect()
    return 0
    for task in task_list:
        print(task)
        

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