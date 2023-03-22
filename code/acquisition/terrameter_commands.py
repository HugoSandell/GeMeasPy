import os
import datetime
import time

from shutil import rmtree

from acquisition import utilities
from settings.config import LOCAL_PATH_TO_DATA, \
                            TERRAMETER_PROJECTS_FOLDER


def start_terrameter_software(connection, display=0):
    connection.send_command_terrameter_software("killall terrameter\n")
    connection.send_command_terrameter_software('export DISPLAY="localhost:{0:2.1f}"\n'.format(display))
    if display == 0:
        print("Starting terrameter software in local (instrument) screen")
    elif display == 10:
        print("Starting terrameter software in remote (X11) screen] ")
    connection.send_command_terrameter_software("terrameter\n")
    utilities.progress_bar(60)
    connection.send_command_terrameter_software("s unattendedmode 1\n")
    clear_buffer(connection, 0)


def terminate_terrameter_software(connection):
	connection.send_command_shell("killall terrameter\n")


def create_project(connection):
    command = "touch /monitoring/new_day"
    connection.send_command_shell(command)
    project_time_stamp = datetime.datetime.now()
    project_name = "{:4d}{:02d}{:02d}_{:02d}{:02d}{:02d}".format(
        project_time_stamp.year, project_time_stamp.month, project_time_stamp.day,
		project_time_stamp.hour, project_time_stamp.minute, project_time_stamp.second)
    new_project_command = "P {:s}\n".format(project_name)
    command = "echo {:} > /monitoring/new_day".format(project_name)
    connection.send_command_shell(command)
    print("Create New Project!")
    connection.send_command_terrameter_software(new_project_command)


def create_task(connection, task):
    print("Create New Task!")
    task_time_stamp = datetime.datetime.now()
    new_task_command = "T {:s} /home/root/protocols/{:s} /home/root/protocols/{:s} {:.0f} {:.0f} {:.0f} 0 0 0 \n".format(
        task["name"], task["spread"], task["protocol"], *task["spacing"])
    connection.send_command_terrameter_software(new_task_command)
    load_settings(connection, task["settings"])


def load_settings(connection, settings):
    load_settings_command = "w /home/root/settings/{0:s} \n".format(settings)
    connection.send_command_terrameter_software(load_settings_command)


def create_station(connection, station_id=1):
    print("Create New Station!")
    new_station_command = "S {0:d} \n".format(station_id)
    connection.send_command_terrameter_software(new_station_command)


def measure(connection, task, logfile, new_measurement=True):
    if "set" in task and "reset" in task:
        utilities.switch_relay(task)
    if new_measurement:
        measuring_start_time = datetime.datetime.now()
        save_time_stamp(connection, measuring_start_time, task["id"])
        log_str = "Measurement started at " + utilities.time_stamp_string(measuring_start_time)
        logfile.write(log_str + "\n")
        print(log_str)
        print("Start Measuring")
        command = "touch /monitoring/task_{0:02d}_started".format(task["id"])
        connection.send_command_shell(command)
    else:
        load_settings(connection, task["settings"])
        measurement_resume_time = datetime.datetime.now()
        log_str = "Measurement resumed at " + utilities.time_stamp_string(measurement_resume_time)
        logfile.write(log_str + "\n")
        print(log_str)
    connection.send_command_terrameter_software('m\n', time_to_sleep=60)
    clear_buffer(connection, 1)


def clear_buffer(connection, mode):
    if mode == 0:
        while True:
            channel_output = connection.read_channel_buffer(1)
            if channel_output == '>':
                break
    elif mode == 1:
        for i in range(5):
            command = "g measure\n"
            connection.send_command_terrameter_software(command)
            connection.read_channel_buffer(1024)
    else:
        print("Wrong input type")


def is_measuring(connection):
    # check if measurement is done
    # clear_buffer(1)
    print("Check if measurement is done...")
    is_measuring_command = "g measure\n"
    connection.send_command_terrameter_software(is_measuring_command)
    channel_output = connection.read_channel_buffer(1024)
    print(channel_output)
    # print(measuring)
    found = channel_output.find("measure\t0")
    if found != -1:
        return False
    else:
        print("Still measuring")
        return True


def is_new_day(connection):
    command = "[ -e /monitoring/new_day ] && echo 'ResumePreviousMeasurement' || echo 'StartNewMeasurement'"
    stdin, stdout, stderr = connection.send_command_shell(command)
    buffer = stdout.readline().strip()
    if buffer.find("ResumePreviousMeasurement") != -1:
        return False
    elif buffer.find("StartNewMeasurement") != -1:
        return True


def save_time_stamp(connection, time_stamp, task_id):
    command = 'echo "{0:d},{1:d},{2:d},{3:d},{4:d},{5:d},{6:d}" > /monitoring/datetime.{7:02d}'.format(
        time_stamp.year, time_stamp.month, time_stamp.day, time_stamp.hour, time_stamp.minute,
        time_stamp.second, time_stamp.microsecond, task_id)
    connection.send_command_shell(command)


def read_time_stamp(connection, task_id):
    command = "more /monitoring/datetime.{0:02d}".format(task_id)
    stdin, stdout, stderr = connection.send_command_shell(command)
    x = stdout.readline().split(',')
    x[-1] = x[-1].strip('\n')
    y = [int(k) for k in x]
    stamp = datetime.datetime(*y)
    return stamp


def task_completed(connection, task_id, logfile):
    measuring_start_time = read_time_stamp(connection, task_id)
    measurement_finish_time = datetime.datetime.now()
    log_str = "Measurement finished at " + utilities.time_stamp_string(measurement_finish_time)
    logfile.write(log_str + "\n")
    print(log_str)
    measurement_duration = measurement_finish_time - measuring_start_time
    log_str = "Measurement lasted for " + utilities.time_stamp_string(measurement_duration, 0)
    logfile.write(log_str + "\n")
    print(log_str)
    command = "rm /monitoring/task_{0:02d}_started".format(task_id)
    connection.send_command_shell(command)
    command = "touch /monitoring/task_{0:02d}_completed".format(task_id)
    connection.send_command_shell(command)
    logfile.write("Task #{0:d} Finished!\n".format(task_id))
    print('Task Completed!')


def is_task_completed(connection, task_id):
    command = "[ -e /monitoring/task_{0:02d}_completed ] && echo 'FileFound' || echo 'NotFound'".format(task_id)
    stdin, stdout, stderr = connection.send_command_shell(command)
    buffer = stdout.readline().strip()
    if buffer.find("FileFound") != -1:
        return True
    elif buffer.find("NotFound") != -1:
        return False


def remove_control_files(connection, task_list):
    print("Removing Monitoring Control Files..")
    command = "more /monitoring/new_day"
    stdin, stdout, stderr = connection.send_command_shell(command)
    time.sleep(1)
    project = stdout.readline().strip()
    for task in task_list:
        command = "rm /monitoring/task_{0:02d}_completed".format(task["id"])
        connection.send_command_shell(command)
        command = "rm /monitoring/datetime.{0:02d}".format(task["id"])
        connection.send_command_shell(command)
    command = "rm /monitoring/new_day"
    connection.send_command_shell(command)
    return project


def transfer_project(connection):
    print("Transferring files...")
    # get project name
    command = "more /monitoring/new_day"
    stdin, stdout, stderr = connection.send_command_shell(command)
    project = stdout.readline().strip()
    # create 'zetsum' file
    command = "mkdir {}/{}/zetsum".format(TERRAMETER_PROJECTS_FOLDER, project)
    stdin, stdout, stderr = connection.send_command_shell(command)
    command = ("echo -e \"This file will be transfered last\n"
               "If this file exists on pc\n"
               "ALL data have been successfully transfered!!\""
               " >> {}/{}/zetsum/zetsum".format(TERRAMETER_PROJECTS_FOLDER, project))
    stdin, stdout, stderr = connection.send_command_shell(command)
    ip = connection.get_ip()
    os.system("sftp -r root@{0:}:{1:}/{3:}/ {2:}/{3:}/".format(
        ip, TERRAMETER_PROJECTS_FOLDER, LOCAL_PATH_TO_DATA, project))
    
    
def check_transfer(connection):
    print("Check if files have been transfered..")
    command = "more /monitoring/new_day"
    stdin, stdout, stderr = connection.send_command_shell(command)
    project = stdout.readline().strip()
    zetsum = "{}/{}/zetsum/zetsum".format(LOCAL_PATH_TO_DATA, project)
    return os.path.isfile(zetsum)
    
    
    
def delete_project(connection, project):
    print("Deleting project from the terrameter..")
    command = "rm -r {}/{}".format(TERRAMETER_PROJECTS_FOLDER, project)
    stdin, stdout, stderr = connection.send_command_shell(command, time_to_sleep=60)
    rmtree("{}/{}/zetsum".format(LOCAL_PATH_TO_DATA, project))


