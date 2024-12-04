import time
from typing import TextIO

from connections import SSHConnection

from acquisition import terrameter_commands as tc
from acquisition import utilities

is_meas_delay = 60
def main(connection: SSHConnection, logfile: TextIO, task_file: str) -> None:
    # Read Info
    task_list = utilities.read_monitoring_tasks(task_file)
    # TODO: This should start only if there are measurements todo.
    tc.start_terrameter_software(connection, display=0)

    # Terrameter logic
    # Check if its (1) New Day (2) Instrument is measuring
    # (3) if it is not a new day and instrument is not measuring THEN resume previous measurement sequence
    logfile.write("Checking if its a New Day or should resume..\n")
    if tc.is_new_day(connection):
        logfile.write("Its a New Day!\n")
        logfile.write("Starting New Project\n")
        print('Starting New Project Sequence')
        tc.create_project(connection)
        # measure all tasks
        for task in task_list:
            logfile.write("Measure Task #{0:d}\n".format(task["id"]))
            tc.create_task(connection, task)
            tc.create_station(connection)
            tc.measure(connection, task, logfile)
            logfile.write("Waiting for measurement to finish...\n")
            while tc.is_measuring(connection):
                time.sleep(is_meas_delay)
            tc.task_completed(connection, task["id"], logfile)
    else:
        # find which task was interupted and finish that task
        print("Check which task left unfinished..")
        logfile.write("Check which task left unfinished..\n")
        for task in task_list:
            print("Checking Task #{0:02d}...".format(task["id"]))
            logfile.write("Checking Task #{0:02d}...\n".format(task["id"]))
            if tc.is_task_completed(connection, task["id"]):
                print("<COMPLETED!!>")
                logfile.write("<COMPLETED!!>\n")
                continue
            else:
                task_interupted = task["id"]
                print("<Task in Progress...>")
                logfile.write("<Task in Progress...>\n")
                print("Resuming Task #{0:02d}".format(task["id"]))
                logfile.write("Resuming Task #{0:02d}\n".format(task["id"]))
                tc.measure(connection, task, logfile, False)
                while tc.is_measuring(connection):
                    time.sleep(10)
                tc.task_completed(connection, task["id"], logfile)
                break
        else:
            # All task are completted!!
            task_interupted = None
        if task_interupted is not None:
            # there ARE remaining tasks to measure
            # measure the remaining tasks in the task list
            print("Measuring the remaining tasks")
            logfile.write("Measuring the remaining tasks\n")
            for task in task_list[task_interupted::]:
                tc.create_task(connection, task)
                # tc.create_station(connection)
                tc.measure(connection, task, logfile)
                while tc.is_measuring(connection):
                    time.sleep(10)
                tc.task_completed(connection, task["id"], logfile)
    tc.terminate_terrameter_software(connection)
    utilities.reset_relay(task_list[0])
    while not tc.check_transfer(connection):
        tc.transfer_project(connection)
    print("Files have succesfully transferred to the pc!")
    project = tc.remove_control_files(connection, task_list)
    tc.delete_project(connection, project)
    print("********************************************")
