import datetime
import json
import os
import sys
import time
from typing import Any, TextIO

from acquisition import subvision_relay
from settings.config import SERVER_BACKUP_CONNECTION_FILE, TERRAMETER_CONNECTION_FILE


def progress_bar(wait_time_seconds: int, ticks=20) -> None:
    # time in seconds
    max_time = wait_time_seconds * 4
    interval = max_time / ticks
    for i in range(max_time):
        n = int(i / interval)
        spaces = ticks - n
        sys.stdout.write('\r    ')
        sys.stdout.write(n * '#' + spaces * ' ' + '{:2.1f}%'.format((i + 1) / max_time * 100))
        sys.stdout.flush()
        time.sleep(0.25)
    sys.stdout.write('\n')
    sys.stdout.flush()


def time_stamp_string_from_timedelta(time_stamp: datetime.timedelta) -> str:
    return "{:02d}:{:02d}:{:02d}".format(int(time_stamp.total_seconds() / 60 // 60),
                                            int(time_stamp.total_seconds() / 60 % 60),
                                            int(time_stamp.total_seconds() % 60))


def time_stamp_string_from_datetime(time_stamp: datetime.datetime) -> str:
    return "{:d}/{:02d}/{:02d} {:02d}:{:02d}:{:02d}".format(
                time_stamp.year, time_stamp.month, time_stamp.day,
                time_stamp.hour, time_stamp.minute, time_stamp.second)



def read_ignore_comments(in_file: TextIO) -> str:
    while True:
        line = in_file.readline()
        if line.startswith('#'):
            continue
        return line.strip()


def read_monitoring_tasks(task_file: str) -> list[dict[str, Any]]:
    with open(task_file, 'r') as file:
        list_of_tasks = []
        task_id = 0
        header = [int(n) for n in read_ignore_comments(file).split()]
        number_of_tasks = header[0]
        match header[1]:
            case 0:
                # no relay switches present
                for task in range(number_of_tasks):
                    task_id += 1
                    task_dict = {"name": read_ignore_comments(file),
                                "spread": read_ignore_comments(file),
                                "protocol": read_ignore_comments(file),
                                "settings": read_ignore_comments(file),
                                "spacing": [float(n) for n in read_ignore_comments(file).split()],
                                "id": task_id}
                    list_of_tasks.append(task_dict)
            case 1:
                # relay switches present
                for task in range(number_of_tasks):
                    task_id += 1
                    task_dict = {"name": read_ignore_comments(file),
                                "spread": read_ignore_comments(file),
                                "protocol": read_ignore_comments(file),
                                "settings": read_ignore_comments(file),
                                "spacing": [float(n) for n in read_ignore_comments(file).split()],
                                "reset": [int(n) for n in read_ignore_comments(file).split()],
                                "set": [int(n) for n in read_ignore_comments(file).split()],
                                "id": task_id}
                    list_of_tasks.append(task_dict)
            case 2:
            # 'new' relay switches present (subvision, 2018)
                for task in range(number_of_tasks):
                    task_id += 1
                    task_dict = {"name": read_ignore_comments(file),
                                "spread": read_ignore_comments(file),
                                "protocol": read_ignore_comments(file),
                                "settings": read_ignore_comments(file),
                                "spacing": [float(n) for n in read_ignore_comments(file).split()],
                                "reset": [n for n in read_ignore_comments(file).split()],
                                "set": [n for n in read_ignore_comments(file).split()],
                                "id": task_id}
                    list_of_tasks.append(task_dict)
            case _:
                print("wrong input")
        return list_of_tasks


def switch_relay(task: dict[str, Any]) -> None:
    print(task["reset"][0])
    if isinstance(task["reset"][0], int):
        for com in task["reset"]:
            print("reset switch c/{}".format(com))
            os.system("RSW16.EXE r/0,0 c/{}".format(com))
            time.sleep(1)
        for com in task["set"]:
            print("set switch c/{}".format(com))
            os.system("RSW16.EXE s/0,0 c/{}".format(com))
            time.sleep(1)
    if isinstance(task["reset"][0], str):
        socket = subvision_relay.connect()
        for com in task["reset"]:
            print("ResetAll({})".format(com))
            socket.send(bytes("ResetAll({})".format(com), 'utf-8'))
            time.sleep(5)
        for com in task["set"]:
            if len(com) == 2:
            # SetAll Command
                print("SetAll({})".format(com))
                socket.send(bytes("SetAll({})".format(com), 'utf-8'))
                time.sleep(5)
            elif len(com) == 3:
                if com[2] == 'o':
                    # SetOdd
                    print("SetOdd({})".format(com[:2]))
                    socket.send(bytes("SetOdd({})".format(com[:2]), 'utf-8'))
                    time.sleep(5)
                elif com[2] == 'e':
                    # SetEven
                    print("SetEven({})".format(com[:2]))
                    socket.send(bytes("SetEven({})".format(com[:2]), 'utf-8'))
                    time.sleep(5)
            elif len(com) > 3:
                # Switch individual electrodes
                print('Function needs to be implemented')
        socket.close()


def reset_relay(task: dict[str, Any], coms: list[int]|None = None) -> None:
    if "reset" not in task.keys():
        return
    if isinstance(task["reset"][0], int):
        if coms is None:
            coms = [1, 2, 3, 4]
        for com in coms:
            os.system("RSW16.EXE r/0,0 c/{}".format(com))
    if isinstance(task["reset"][0], str):
        pass


def read_terrameter_connection_parameters() -> dict[str, Any]:
    with open(TERRAMETER_CONNECTION_FILE, 'r') as file:
        instrument_settings = json.load(file)
        return instrument_settings


def read_server_connection_parameters() -> dict[str, Any]:
    with open(SERVER_BACKUP_CONNECTION_FILE, 'r') as file:
        server_backup_settings = json.load(file)
        return server_backup_settings


def wait(start_time: str) -> None:
    time_split = start_time.split(':')
    start_time_minutes = int(time_split[0])*60 + int(time_split[1])
    now = datetime.datetime.now()
    minutes = now.hour*60 + now.minute
    if minutes > start_time_minutes:
        start_time_minutes += 24 * 60
    wait_time = start_time_minutes - minutes
    time.sleep(wait_time*60)

# Returns current integer timestamp in milliseconds as hex string
def timestamp_hex() -> str:
    nano_to_milli = 1.0 / 1_000_000
    timestamp = int(time.time_ns() * nano_to_milli)
    return f'{timestamp:0+x}'