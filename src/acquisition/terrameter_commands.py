import datetime
import os
import time
from shutil import rmtree
from typing import Any, TextIO

from acquisition.connections import SSHConnection

from acquisition import utilities
from settings.config import LOCAL_PATH_TO_DATA, TERRAMETER_PROJECTS_FOLDER, TERRAMETER_MONITORING_FOLDER


def start_terrameter_software(connection: SSHConnection, display=0) -> None:
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


def terminate_terrameter_software(connection: SSHConnection) -> None:
	connection.send_command_shell("killall terrameter\n")


def create_project(connection: SSHConnection) -> None:
    command = f"touch {TERRAMETER_MONITORING_FOLDER}/new_day"
    connection.send_command_shell(command)
    project_time_stamp = datetime.datetime.now()
    project_name = "{:4d}{:02d}{:02d}_{:02d}{:02d}{:02d}".format(
        project_time_stamp.year, project_time_stamp.month, project_time_stamp.day,
		project_time_stamp.hour, project_time_stamp.minute, project_time_stamp.second)
    new_project_command = "P {:s}\n".format()
    command = f"echo {project_name} > {TERRAMETER_MONITORING_FOLDER}/new_day"
    connection.send_command_shell(command)
    print("Create New Project!")
    connection.send_command_terrameter_software(new_project_command)


def create_task(connection: SSHConnection, task: dict[str, str]) -> None:
    print("Create New Task!")
    #task_time_stamp = datetime.datetime.now()
    new_task_command = "T {:s} /home/root/protocols/{:s} /home/root/protocols/{:s} {:.0f} {:.0f} {:.0f} 0 0 0 \n".format(
        task["name"], task["spread"], task["protocol"], *task["spacing"])
    connection.send_command_terrameter_software(new_task_command)
    load_settings(connection, task["settings"])


def load_settings(connection: SSHConnection, settings: str) -> None:
    load_settings_command = "w /home/root/settings/{0:s} \n".format(settings)
    connection.send_command_terrameter_software(load_settings_command)


def create_station(connection: SSHConnection, station_id=1) -> None:
    print("Create New Station!")
    new_station_command = "S {0:d} \n".format(station_id)
    connection.send_command_terrameter_software(new_station_command)


def measure(connection: SSHConnection, task, logfile: TextIO, new_measurement: bool = True) -> None:
    if "set" in task and "reset" in task:
        utilities.switch_relay(task)
    if new_measurement:
        measuring_start_time = datetime.datetime.now()
        save_time_stamp(connection, measuring_start_time, task["id"])
        log_str = "Measurement started at " + utilities.time_stamp_string_from_datetime(measuring_start_time)
        logfile.write(log_str + "\n")
        print(log_str)
        print("Start Measuring")
        command = f"touch {TERRAMETER_MONITORING_FOLDER}/task_{0:02d}_started".format(task["id"])
        connection.send_command_shell(command)
    else:
        load_settings(connection, task["settings"])
        measurement_resume_time = datetime.datetime.now()
        log_str = "Measurement resumed at " + utilities.time_stamp_string_from_datetime(measurement_resume_time)
        logfile.write(log_str + "\n")
        print(log_str)
    connection.send_command_terrameter_software('m\n', time_to_sleep=60)
    clear_buffer(connection, 1)


def clear_buffer(connection: SSHConnection, mode: int) -> None:
    match mode:
        case 0:
            while True:
                channel_output = connection.read_channel_buffer(1)
                if channel_output == '>':
                    break
        case 1:
            for i in range(5):
                command = "g measure\n"
                connection.send_command_terrameter_software(command)
                connection.read_channel_buffer(1024)
        case _:
            print("Wrong input type")


def is_measuring(connection: SSHConnection) -> bool:
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


def is_new_day(connection: SSHConnection) -> None | bool:
    command = f"[ -e {TERRAMETER_MONITORING_FOLDER}/new_day ] && echo 'ResumePreviousMeasurement' || echo 'StartNewMeasurement'"
    stdin, stdout, stderr = connection.send_command_shell(command)
    buffer = stdout.readline().strip()
    if buffer.find("ResumePreviousMeasurement") != -1:
        return False
    elif buffer.find("StartNewMeasurement") != -1:
        return True


def save_time_stamp(connection: SSHConnection, time_stamp: datetime.datetime, task_id: int) -> None:
    command = f'echo "{0:d},{1:d},{2:d},{3:d},{4:d},{5:d},{6:d}" > {TERRAMETER_MONITORING_FOLDER}/datetime.{7:02d}'.format(
        time_stamp.year, time_stamp.month, time_stamp.day, time_stamp.hour, time_stamp.minute,
        time_stamp.second, time_stamp.microsecond, task_id)
    connection.send_command_shell(command)


def read_time_stamp(connection: SSHConnection, task_id: int) -> datetime.datetime:
    command = f"more {TERRAMETER_MONITORING_FOLDER}/datetime.{0:02d}".format(task_id)
    stdin, stdout, stderr = connection.send_command_shell(command)
    datetime_string = stdout.readline().strip().split(',')

    if len(datetime_string) == 7:
        year, month, day, hour, minute, second, microsecond = [int(k) for k in datetime_string]
        stamp = datetime.datetime(year, month, day, hour, minute, second, microsecond)
        return stamp
    return datetime.datetime.now()


def task_completed(connection: SSHConnection, task_id: int, logfile: TextIO) -> None:
    measuring_start_time = read_time_stamp(connection, task_id)
    measurement_finish_time = datetime.datetime.now()
    log_str = "Measurement finished at " + utilities.time_stamp_string_from_datetime(measurement_finish_time)
    logfile.write(log_str + "\n")
    print(log_str)
    measurement_duration = measurement_finish_time - measuring_start_time
    log_str = "Measurement lasted for " + utilities.time_stamp_string_from_timedelta(measurement_duration)
    logfile.write(log_str + "\n")
    print(log_str)
    command = f"rm {TERRAMETER_MONITORING_FOLDER}/task_{0:02d}_started".format(task_id)
    connection.send_command_shell(command)
    command = f"touch {TERRAMETER_MONITORING_FOLDER}/task_{0:02d}_completed".format(task_id)
    connection.send_command_shell(command)
    logfile.write("Task #{0:d} Finished!\n".format(task_id))
    print('Task Completed!')


def is_task_completed(connection: SSHConnection, task_id: int) -> None | bool:
    command = f"[ -e {TERRAMETER_MONITORING_FOLDER}/task_{0:02d}_completed ] && echo 'FileFound' || echo 'NotFound'".format(task_id)
    stdin, stdout, stderr = connection.send_command_shell(command)
    buffer = stdout.readline().strip()
    if buffer.find("FileFound") != -1:
        return True
    elif buffer.find("NotFound") != -1:
        return False


def remove_control_files(connection: SSHConnection, task_list: list[dict[str, Any]]) -> str:
    print("Removing Monitoring Control Files..")
    command = f"more {TERRAMETER_MONITORING_FOLDER}/new_day"
    stdin, stdout, stderr = connection.send_command_shell(command)
    time.sleep(1)
    project = 'test' #stdout.readline().strip()
    for task in task_list:
        command = f"rm {TERRAMETER_MONITORING_FOLDER}/task_{0:02d}_completed".format(task["id"])
        connection.send_command_shell(command)
        command = f"rm {TERRAMETER_MONITORING_FOLDER}/datetime.{0:02d}".format(task["id"])
        connection.send_command_shell(command)
    command = f"rm {TERRAMETER_MONITORING_FOLDER}/new_day"
    connection.send_command_shell(command)
    return project


def transfer_project(connection: SSHConnection) -> None:
    print("Transferring files...")
    # get project name
    command = f"more {TERRAMETER_MONITORING_FOLDER}/new_day"
    stdin, stdout, stderr = connection.send_command_shell(command)
    project = 'test' #stdout.readline().strip()
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


def check_transfer(connection: SSHConnection) -> bool:
    print("Check if files have been transfered..")
    command = f"more {TERRAMETER_MONITORING_FOLDER}/new_day"
    stdin, stdout, stderr = connection.send_command_shell(command)
    project = 'test'#stdout.readline().strip()
    zetsum = "{}/{}/zetsum/zetsum".format(LOCAL_PATH_TO_DATA, project)
    return os.path.isfile(zetsum)


def delete_project(connection: SSHConnection, project: str) -> None:
    print("Deleting project from the terrameter..")
    command = "rm -r {}/{}".format(TERRAMETER_PROJECTS_FOLDER, project)
    stdin, stdout, stderr = connection.send_command_shell(command, time_to_sleep=60)
    rmtree("{}/{}/zetsum".format(LOCAL_PATH_TO_DATA, project))


