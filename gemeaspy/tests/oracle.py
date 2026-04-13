"""This module is responsible for reviewing test execution data and determining whether or not a failure has occured"""

from dataclasses import dataclass
import re

from gemeaspy.tests import _logging
from gemeaspy.tests.generator.parameter_spec import AcquisitionParameterSpec
from gemeaspy.tests.setup_config import ConfigState
from gemeaspy.tests.generator.test_case import AcquisitionTestCase, TestCase

# Regular expressions for matching a "class" of paramters
RE_TASK = re.compile(r"taskfile(?P<file>\d+)_task(?P<task>\d+)_(?P<property>spread|protocol|name|settings|spacing)")

@dataclass
class OracleResult:
    ok: bool
    msg: str = ""
    def __bool__(self) -> bool:
        return self.ok

# Common checks
def _find_stdout_error_message(stdout: str) -> str | None:
    """Checks returns first line with reported error, or None if one wasn't found"""
    lines = stdout.splitlines()
    error_lines = list(filter(lambda s: "Error: " in s, lines))
    if len(error_lines) <= 0:
        return None
    return error_lines[0]

def _was_project_transferred() -> bool:
    """Checks whether the project has been transferred correctly"""
    raise NotImplementedError()
    
# Evaluators
def _evaluate_any(config_state: ConfigState) -> OracleResult:
    """Checks properties that should hold for all cases"""
    if config_state.data_invalid_is_modified():
        return OracleResult(False, "SUT modified file configured as LOCAL_PATH_TO_DATA")
    return OracleResult(True)

def _evaluate_valid(test_data: TestCase, stdout: str, stderr:str) -> OracleResult:
    """Checks that results are consistent with valid inputs"""
    # Find any faulty states
    err_pos = stdout.find("Error: ")
    if err_pos >= 0:
        _logging.info(f"SUT failed with stdout:\n{stdout}\nstderr:\n{stderr}")
        return OracleResult(False, stdout[err_pos:].splitlines()[0])
    # Looks clean
    return OracleResult(True)


def _evaluate_arg_task_files(
    test_data: AcquisitionTestCase, stdout: str
) -> OracleResult:
    value = test_data.parameters.arg_task_files

    if not (msg := _find_stdout_error_message(stdout)):
        return OracleResult(
            False, f"No error message found for invalid arg_task_files={repr(value)}"
        )

    if len(value) == 0:
        if "No task file given" in msg:
            return OracleResult(True)
    else:
        raise NotImplementedError(
            f"Value {repr(value)} not implemented in arg_task_files evaluator"
        )

    return OracleResult(
        False,
        f"Unexpected error message for invalid arg_task_files={repr(value)}: {msg}",
    )


def _evaluate_port(test_data: AcquisitionTestCase, stdout: str, stderr:str) -> OracleResult:
    """Bad port number"""
    if _find_stdout_error_message(stdout):
        return OracleResult(True)
    value = test_data.parameters.connection_port
    return OracleResult(False, f"No error message found for invalid connection port value {repr(value)}")

def _evaluate_task_property(test_case: AcquisitionTestCase, file: int, task: int, property: str, stdout: str) -> OracleResult:
    """Any invalid property of a task"""
    parameter_name = f"taskfile{file}_task{task}_{property}"
    parameter_value = test_case.parameters[parameter_name]
    msg_no_error_found = f"No error message found for invalid task {property} {parameter_name}={repr(parameter_value)}"
    
    match property:
        case "name":
            if _find_stdout_error_message(stdout):
                return OracleResult(True)
            return OracleResult(False, msg_no_error_found)
        case "settings":
            if _find_stdout_error_message(stdout):
                return OracleResult(True)
            return OracleResult(False, msg_no_error_found)
        case "spread":
            if _find_stdout_error_message(stdout):
                return OracleResult(True)
            return OracleResult(False, msg_no_error_found)
        case "protocol":
            if _find_stdout_error_message(stdout):
                return OracleResult(True)
            return OracleResult(False, msg_no_error_found)
        case "spacing":
            if _find_stdout_error_message(stdout):
                return OracleResult(True)
            return OracleResult(False, msg_no_error_found)
    return OracleResult(True)

def evaluate_test(
    test_data: AcquisitionTestCase,
    config_state: ConfigState,
    task_files: list[str],
    stdout: str,
    stderr: str,
) -> OracleResult:
    result = _evaluate_any(config_state)
    if not result:
        return result

    param_spec = AcquisitionParameterSpec()
    invalid_parameter = test_data.invalid_parameter

    match invalid_parameter:
        case None:
            return _evaluate_valid(test_data, stdout, stderr)
        case "arg_task_files":
            return _evaluate_arg_task_files(test_data, stdout)
        case "connection_port":
            return _evaluate_port(test_data, stdout, stderr)
        case p if (match := re.match(RE_TASK, p)) != None:
            file = int(match.group("file"))
            task = int(match.group("task"))
            property = str(match.group("property"))
            return _evaluate_task_property(test_data, file, task, property, stdout)
        case _:
            if invalid_parameter not in param_spec:
                return OracleResult(False, f"invalid_parameter set to invalid value {repr(invalid_parameter)}")
            if (msg := _find_stdout_error_message(stdout)) is not None:
                _logging.warning(
                    f"No specific evaluator exists for invalid parameter {invalid_parameter}. Assuming this is the expected error: {msg}"
                )
                return OracleResult(True)
            raise NotImplementedError(f"Invalid value {invalid_parameter}={repr(test_data.parameters[invalid_parameter])} not implemented in Oracle.")