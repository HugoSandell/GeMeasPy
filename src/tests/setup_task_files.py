import os
import sys
import tempfile

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests import parameter_spec
from tests.test_case import TestCase
from tests.util import random_string


def _create_task_file(test: TestCase, file_no: int):
    prefix = f"taskfile{file_no}_"
    number_of_tasks = test[f"{prefix}number_of_tasks"]
    relay_type = test[f"{prefix}relay_type"]

    # TODO cleanup
    fd, path = tempfile.mkstemp(prefix="gemeaspytest_task_file_")

    with open(fd, "w") as f:
        f.write(f"{number_of_tasks} {relay_type}\n")

        if type(number_of_tasks) is not int:
            number_of_tasks = 0

        for taskid in range(1, number_of_tasks + 1):
            task_prefix = f"{prefix}task{taskid}_"
            f.write(f"{test[f'{task_prefix}name']}\n")

            match test[f"{task_prefix}spread"]:
                case parameter_spec.INVALID_FILE:
                    f.write(f"{random_string()}\n")
                case parameter_spec.VALID_SPREADFILE:
                    f.write("2X21.xml\n")
                case x:
                    f.write(f"{x}\n")

            match test[f"{task_prefix}protocol"]:
                case parameter_spec.INVALID_FILE:
                    f.write(f"{random_string()}\n")
                case parameter_spec.VALID_PROTOCOLFILE:
                    f.write("Gradient_2x21.xml\n")
                case x:
                    f.write(f"{x}\n")

            match test[f"{task_prefix}settings"]:
                case parameter_spec.INVALID_FILE:
                    f.write(f"{random_string()}\n")
                case parameter_spec.VALID_SETTINGSFILE:
                    f.write("testing1s.settings\n")
                case x:
                    f.write(f"{x}\n")

            f.write(f"{test[f'{task_prefix}spacing']}\n")

    return path


def resolve_task_files(test: TestCase):
    created_task_files = {}
    task_files = []

    def _get_or_create_task_file(file_no: int):
        if file_no not in created_task_files:
            created_task_files[file_no] = _create_task_file(test, file_no)
        return created_task_files[file_no]

    if not type(test["arg_task_files"]) is list:
        raise TypeError("Parameter 'arg_task_files' has an invalid type")

    for task_file in test["arg_task_files"]:
        match task_file:
            case parameter_spec.INVALID_FILE:
                task_files.append(random_string())
            case parameter_spec.VALID_TASKFILE1:
                task_files.append(_get_or_create_task_file(1))
            case parameter_spec.VALID_TASKFILE2:
                task_files.append(_get_or_create_task_file(2))
            case x:
                task_files.append(x)

    return task_files


if __name__ == "__main__":
    print(
        resolve_task_files(
            {
                "arg_task_files": [
                    parameter_spec.VALID_TASKFILE1,
                    parameter_spec.INVALID_FILE,
                ],
                "taskfile1_number_of_tasks": "2",
                "taskfile1_relay_type": "",
                "taskfile1_task1_name": "Task1",
                "taskfile1_task1_spread": parameter_spec.VALID_SPREADFILE,
                "taskfile1_task1_protocol": parameter_spec.VALID_PROTOCOLFILE,
                "taskfile1_task1_settings": parameter_spec.VALID_SETTINGSFILE,
                "taskfile1_task1_spacing": "1 1 1",
                "taskfile1_task2_name": "#TaskX",
                "taskfile1_task2_spread": parameter_spec.INVALID_FILE,
                "taskfile1_task2_protocol": parameter_spec.INVALID_FILE,
                "taskfile1_task2_settings": parameter_spec.INVALID_FILE,
                "taskfile1_task2_spacing": "1 1 1 1",
            }
        )
    )
