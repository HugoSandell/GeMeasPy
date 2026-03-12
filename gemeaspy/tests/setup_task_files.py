import tempfile
import typing

from gemeaspy.tests import parameter_spec
from gemeaspy.tests.test_case import AcquisitionTestCase
from gemeaspy.tests.util import random_string

def _replace_file_placeholder(value: str):
    match value:
        case parameter_spec.INVALID_FILE:
            return random_string()
        case x:
            return x


def _create_task_file(test_case: AcquisitionTestCase, file_no: int):
    prefix = f"taskfile{file_no}_"
    
    def param_as_str(param: str, prefix: str = prefix) -> str:
        """Get the given attribute of test case as str or throw an exception."""
        return str(getattr(test_case, prefix + param))
            
    number_of_tasks = param_as_str("number_of_tasks")
    relay_type = param_as_str("relay_type")

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
        f.write(f"{param_as_str('name', task_prefix)}\n")
        f.write(f"{_replace_file_placeholder(param_as_str('spread', task_prefix))}\n")
        f.write(f"{_replace_file_placeholder(param_as_str('protocol', task_prefix))}\n")
        f.write(f"{_replace_file_placeholder(param_as_str('settings', task_prefix))}\n")
        f.write(f"{param_as_str('spacing', task_prefix)}\n")
        
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
