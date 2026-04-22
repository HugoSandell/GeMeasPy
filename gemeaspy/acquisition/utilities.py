import datetime
from io import StringIO, TextIOWrapper
import json
import os
import sys
import time
from typing import Any, TextIO

from gemeaspy.acquisition import subvision_relay
from gemeaspy.acquisition.error import TaskFileIOError, TaskFileParseError
from gemeaspy.settings import config


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
        sleep_unless_testing(0.25)
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



def read_ignore_comments(in_file: TextIO, value_name: str  = "value") -> str:
    """
        Returns the next non-comment line of in_file, stripped.
        value_name is an identifier for the expected value, used in any raised exception.
        A TaskFileParseError exception is raised if EOF is reached.
    """
    while True:
        line = in_file.readline()
        print(line)
        if line == "":  # EOF
            raise TaskFileParseError(f"Task file ended before expected {value_name} could be read")
        if line.strip() == "": # Empty line -- skip
            continue
        if line.startswith('#'):
            continue
        return line.strip()

def read_spacing(data: StringIO, filename: str):
    spacing_str = read_ignore_comments(data, "spacing").split()
    try: 
        spacing = [float(n) for n in spacing_str]
        if len(spacing) != 3:
            raise ValueError()
        return spacing
    except ValueError as e:
        raise TaskFileParseError(f"Invalid spacing {spacing_str!r}", filename)

def read_monitoring_tasks(task_file: str) -> list[dict[str, Any]]:
    contents = StringIO()
    try:
        with open(task_file, 'r') as file:
            contents.write(file.read())
            contents.seek(0)
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise TaskFileIOError(file=task_file)

    # Header format: "<number_of_tasks> <relay_type>" (two integers separated by a space)
    list_of_tasks = []
    task_id = 0
    
    try:
        header_line = read_ignore_comments(contents)
        parts = header_line.split()
        number_of_tasks = int(parts[0])
        relay_type = int(parts[1])
    except (ValueError, IndexError, TaskFileParseError):
        raise TaskFileParseError(f"Invalid task file header in {task_file!r}", file=task_file)

    def _read_task_name() -> str:
        """Read the name field of the next task, raising an error if EOF is reached."""
        try:
            name = read_ignore_comments(contents)
        except TaskFileParseError:
            raise TaskFileParseError(
                f"Declared number of tasks does not match actual number of tasks in {task_file!r}",
                file=task_file,
            )
        return name

    match relay_type:
        case 0:
            # no relay switches present
            for task in range(number_of_tasks):
                task_id += 1
                task_dict = {}
                task_dict["name"] = _read_task_name()
                task_dict["spread"] = read_ignore_comments(contents, "spread file path")
                task_dict["protocol"] = read_ignore_comments(contents, "file path")
                task_dict["settings"] = read_ignore_comments(contents, "file path")
                task_dict["spacing"] = read_spacing(contents, task_file)
                task_dict["id"] = task_id
                list_of_tasks.append(task_dict)
        case 1:
            # relay switches present
            for task in range(number_of_tasks):
                task_id += 1
                task_dict = {}
                task_dict["name"] = _read_task_name()
                task_dict["spread"] = read_ignore_comments(contents, "spread file path")
                task_dict["protocol"] = read_ignore_comments(contents, "file path")
                task_dict["settings"] = read_ignore_comments(contents, "file path")
                task_dict["spacing"] = read_spacing(contents, task_file)
                task_dict["reset"] = [int(n) for n in read_ignore_comments(contents, "relay reset").split()]
                task_dict["set"] = [int(n) for n in read_ignore_comments(contents, "relay set").split()]
                task_dict["id"] = task_id
                list_of_tasks.append(task_dict)
        case 2:
            # 'new' relay switches present (subvision, 2018)
            for task in range(number_of_tasks):
                task_id += 1
                task_dict = {}
                task_dict["name"] = _read_task_name()
                task_dict["spread"] = read_ignore_comments(contents, "spread file path")
                task_dict["protocol"] = read_ignore_comments(contents, "file path")
                task_dict["settings"] = read_ignore_comments(contents, "file path")
                task_dict["spacing"] = read_spacing(contents, task_file)
                task_dict["reset"] = [int(n) for n in read_ignore_comments(contents, "relay reset").split()]
                task_dict["set"] = [int(n) for n in read_ignore_comments(contents, "relay set").split()]
                task_dict["id"] = task_id
                list_of_tasks.append(task_dict)
        case _:
            raise TaskFileParseError(f"Invalid relay type {relay_type}")

    # Check for remaining non-comment content: indicates declared count < actual
    bad_task_count = len(list_of_tasks) != number_of_tasks
    remaining = contents.read()
    if bad_task_count or any(line.strip() and not line.strip().startswith('#') for line in remaining.splitlines()):
        raise TaskFileParseError(
            f"Declared number of tasks does not match actual number of tasks in {task_file!r}",
            file=task_file,
        )
    return list_of_tasks


def switch_relay(task: dict[str, Any]) -> None:
    print(task["reset"][0])
    if isinstance(task["reset"][0], int):
        for com in task["reset"]:
            print("reset switch c/{}".format(com))
            os.system("RSW16.EXE r/0,0 c/{}".format(com))
            sleep_unless_testing(1)
        for com in task["set"]:
            print("set switch c/{}".format(com))
            os.system("RSW16.EXE s/0,0 c/{}".format(com))
            sleep_unless_testing(1)
    if isinstance(task["reset"][0], str):
        socket = subvision_relay.connect()
        for com in task["reset"]:
            print("ResetAll({})".format(com))
            socket.send(bytes("ResetAll({})".format(com), 'utf-8'))
            sleep_unless_testing(5)
        for com in task["set"]:
            if len(com) == 2:
            # SetAll Command
                print("SetAll({})".format(com))
                socket.send(bytes("SetAll({})".format(com), 'utf-8'))
                sleep_unless_testing(5)
            elif len(com) == 3:
                if com[2] == 'o':
                    # SetOdd
                    print("SetOdd({})".format(com[:2]))
                    socket.send(bytes("SetOdd({})".format(com[:2]), 'utf-8'))
                    sleep_unless_testing(5)
                elif com[2] == 'e':
                    # SetEven
                    print("SetEven({})".format(com[:2]))
                    socket.send(bytes("SetEven({})".format(com[:2]), 'utf-8'))
                    sleep_unless_testing(5)
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
    with open(config.TERRAMETER_CONNECTION_FILE, "r") as file:
        instrument_settings = json.load(file)
        return instrument_settings


def read_server_connection_parameters() -> dict[str, Any]:
    with open(config.SERVER_BACKUP_CONNECTION_FILE, "r") as file:
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
    sleep_unless_testing(wait_time * 60)


def sleep_unless_testing(time_seconds: float) -> None:
    if "USETERRAMETEREMULATOR" not in os.environ:
        time.sleep(time_seconds)


def timestamp_hex() -> str:
    """Returns current integer timestamp in milliseconds as hex string"""
    nano_to_milli = 1.0 / 1_000_000
    timestamp = int(time.time_ns() * nano_to_milli)
    return f"{timestamp:016x}"
