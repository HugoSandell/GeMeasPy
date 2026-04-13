"""For generating tasklist files from test case parameters."""

import os
import tempfile
from tempfile import _TemporaryFileWrapper, TemporaryDirectory

from collections.abc import Callable
from typing import Any

from gemeaspy.tests.generator import parameter_spec
from gemeaspy.tests.generator.int_field_error import IntFieldError
from gemeaspy.tests.generator.test_case import AcquisitionTestCase, AcquisitionTestCaseParameters
from gemeaspy.tests.generator.util import random_string


def _replace_file_placeholder(value: str, invalid_prefix: str) -> str:
    match value:
        case parameter_spec.INVALID_FILE:
            return f"{invalid_prefix}_{random_string()}"
        case x:
            return x


def _create_task_file(test_case: AcquisitionTestCase, file_no: int):
    prefix = f"taskfile{file_no}_"

    def param[T](param: str, t: Callable[[Any], T], prefix: str = prefix) -> T:
        """Get the given attribute of test case as `T` or throw an exception."""
        return t(test_case.parameters[prefix + param])

    number_of_tasks = param("number_of_tasks", int)
    num_tasks_error = param("number_of_tasks_error", IntFieldError.__getitem__)
    relay_type = param("relay_type", str)

    f = tempfile.NamedTemporaryFile(
        mode="w", prefix="gemeaspytest_task_file_", delete_on_close=False
    )
    f.write(f"{num_tasks_error.resolve(number_of_tasks)} {relay_type}\n")

    for taskid in range(1, number_of_tasks + 1):
        task_prefix = f"{prefix}task{taskid}_"

        def task_param(name: str, is_file: bool) -> str:
            value = param(name, str, task_prefix)
            if is_file:
                return _replace_file_placeholder(value, name)
            else:
                return value

        f.write(f"{task_param('name', False)}\n")
        f.write(f"{task_param('spread', True)}\n")
        f.write(f"{task_param('protocol', True)}\n")
        f.write(f"{task_param('settings', True)}\n")
        f.write(f"{task_param('spacing', False)}\n")

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

    if type(test.parameters.arg_task_files) is not list:
        raise TypeError("Parameter 'arg_task_files' has an invalid type")

    for task_file in test.parameters.arg_task_files:
        match task_file:
            case parameter_spec.INVALID_FILE:
                task_files.append(f"task_file_{random_string()}")
            case parameter_spec.VALID_TASKFILE1:
                task_files.append(_get_or_create_task_file(1))
            case parameter_spec.VALID_TASKFILE2:
                task_files.append(_get_or_create_task_file(2))
            case x:
                task_files.append(x)

    def _cleanup():
        for f in tempfiles:
            if isinstance(f, TemporaryDirectory):
                f.cleanup()
            elif isinstance(f, _TemporaryFileWrapper):
                os.unlink(f.name)

    return task_files, _cleanup


if __name__ == "__main__":
    test_case = AcquisitionTestCase(_parameters=AcquisitionTestCaseParameters(
        arg_task_files=[parameter_spec.VALID_TASKFILE1, parameter_spec.INVALID_FILE],
        taskfile1_number_of_tasks=2,
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
    ))
    print(resolve_task_files(test_case))
