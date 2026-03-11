import os
import sys
import tempfile

sys.path.insert(1, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests import parameter_spec
from tests.test_case import AcquisitionTestCase
from tests.util import random_string


def _create_task_file(test: AcquisitionTestCase, file_no: int):
    prefix = f"taskfile{file_no}_"
    number_of_tasks = test[f"{prefix}number_of_tasks"]
    relay_type = test[f"{prefix}relay_type"]

    f = tempfile.NamedTemporaryFile(
        mode="w", prefix="gemeaspytest_task_file_", delete_on_close=False
    )
    f.write(f"{number_of_tasks} {relay_type}\n")

    try:
        number_of_tasks = int(number_of_tasks)
    except ValueError:
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

    f.close()
    return f


def resolve_task_files(test: AcquisitionTestCase):
    tempfiles = []
    created_task_files = {}
    task_files = []

    def _get_or_create_task_file(file_no: int):
        if file_no not in created_task_files:
            f = _create_task_file(test, file_no)
            tempfiles.append(f)
            created_task_files[file_no] = f.name
        return created_task_files[file_no]

    if type(test.arg_task_files) is not list:
        raise TypeError("Parameter 'arg_task_files' has an invalid type")

    for task_file in test.arg_task_files:
        match task_file:
            case parameter_spec.INVALID_FILE:
                task_files.append(random_string())
            case parameter_spec.VALID_TASKFILE1:
                task_files.append(_get_or_create_task_file(1))
            case parameter_spec.VALID_TASKFILE2:
                task_files.append(_get_or_create_task_file(2))
            case x:
                task_files.append(x)

    def _cleanup():
        for f in tempfiles:
            f.__exit__(None, None, None)

    return task_files, _cleanup


if __name__ == "__main__":
    test_case = AcquisitionTestCase(
        arg_task_files=[parameter_spec.VALID_TASKFILE1, parameter_spec.INVALID_FILE],
        taskfile1_number_of_tasks="2",
        taskfile1_relay_type="",
        taskfile1_task1_name="Task1",
        taskfile1_task1_spread=parameter_spec.VALID_SPREADFILE,
        taskfile1_task1_protocol=parameter_spec.VALID_PROTOCOLFILE,
        taskfile1_task1_settings=parameter_spec.VALID_SETTINGSFILE,
        taskfile1_task1_spacing="1 1 1",
        taskfile1_task2_name="#TaskX",
        taskfile1_task2_spread=parameter_spec.INVALID_FILE,
        taskfile1_task2_protocol=parameter_spec.INVALID_FILE,
        taskfile1_task2_settings=parameter_spec.INVALID_FILE,
        taskfile1_task2_spacing="1 1 1 1",
    )
    print(resolve_task_files(test_case))
