"""This module is responsible for reviewing test execution data and determining whether or not a failure has occurred"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from types import FrameType
from typing import NoReturn
import inspect

from gemeaspy.tests import _logging
from gemeaspy.tests.generator import parameter_spec
from gemeaspy.tests.generator.int_field_error import IntFieldError
from gemeaspy.tests.generator.parameter_spec import (
    INVALID_FILE,
    AcquisitionParameterSpec,
)
from gemeaspy.tests.generator.test_case import AcquisitionTestCase, TestCase
from gemeaspy.tests.setup_config import ConfigState
from gemeaspy.tests.terrameter_model.behaviors import TerrameterBehavior


class Port22Status(Enum):
    """State of port 22 on the test host, detected once per session.

    Set by the patch_transport_default_port fixture and read by the oracle
    to select the right expected error when connection_port is None
    (i.e. paramiko would default to port 22).
    """
    CLOSED = auto()            # connection refused / timeout / unreachable
    NON_SSH = auto()           # something listening but SSH handshake fails
    SSH_AUTH_REQUIRED = auto() # SSH up, rejects our credentials
    SSH_OPEN = auto()          # SSH up, accepts a valid test credential

port22_status: Port22Status = Port22Status.CLOSED

# Regular expressions for matching a "class" of parameters
RE_TASK = re.compile(r"taskfile(?P<file>\d+)_task(?P<task>\d+)_(?P<property>spread|protocol|name|settings|spacing)")



@dataclass
class OracleResult:
    ok: bool
    msg: str = ""
    def __init__(self, ok: bool, msg: str = "", context: int = 0):
        """context is how many steps out to get the frame, 0 being the call to this constructor"""
        self.ok = ok
        self.msg = msg
        # To find the origin of this OracleResult
        self.frame: None | FrameType = inspect.currentframe()
        """A frame to help identify where the result was determined"""
        for _ in range(context + 1):
            if self.frame is not None:
                self.frame = self.frame.f_back
            else:
                break
            
    def __bool__(self) -> bool:
        return self.ok

def _raise_unimplemented(test_case: TestCase) -> NoReturn:
    param_name = test_case.invalid_parameter
    if param_name is None or param_name not in test_case:
        raise ValueError(f"invalid_parameter {param_name!r} not found in test case.")
    param_value = test_case[param_name]
    raise NotImplementedError(f"Invalid value {param_name}={param_value!r} not implemented in Oracle.")

# Common checks
def _find_stdout_error_message(stdout: str) -> str | None:
    """Checks returns first line with reported error, or None if one wasn't found"""
    lines = stdout.splitlines()
    error_lines = list(filter(lambda s: "Error: " in s, lines))
    if len(error_lines) <= 0:
        return None
    return error_lines[0]

def _expect_error_message(test_case: TestCase, expected_error: str, stdout: str, allow_without_error = False) -> OracleResult:
    """Evaluate stdout, expecting an error message and return an OracleResult accordingly."""
    param_name = test_case.invalid_parameter
    param_value = test_case[str(param_name)]
    error_message = _find_stdout_error_message(stdout)
    if error_message is None:
        if allow_without_error:
            return OracleResult(True, context=1)
    if error_message is not None and expected_error.lower() in error_message.lower():
        return OracleResult(True, context=1)
    else:
        _logging.info(f"Expected '{expected_error}' in stdout, got:\n{stdout}")
        return OracleResult(False, f"Did not find error message containing {expected_error!r} in output for invalid parameter {param_name} = {param_value!r}.", context=1)

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
    invalid_taskfile = str(test_data.invalid_parameter)
    invalid_value: str = str(test_data[invalid_taskfile])

    if not (msg := _find_stdout_error_message(stdout)):
        return OracleResult(
            False, f"No error message found for invalid {invalid_taskfile}={invalid_value!r}"
        )

    if INVALID_FILE in invalid_value:
        return _expect_error_message(test_data, "Failed to read task file", stdout)
    
    return OracleResult(
        False,
        f"Unexpected error message for invalid {invalid_taskfile}={invalid_value!r}: {msg}",
    )

def _evaluate_number_of_tasks_error(test_data: AcquisitionTestCase, stdout: str, stderr: str) -> OracleResult:
    if not test_data.invalid_parameter:
        raise ValueError("Test must have invalid parameter")
    elif test_data.invalid_parameter not in ("taskfile1_number_of_tasks_error", "taskfile2_number_of_tasks_error"):
        raise ValueError("Invalid parameter must be taskfile#_number_of_tasks_error")
    error_type = test_data[test_data.invalid_parameter]

    match error_type:
        case IntFieldError.CORRECT.name:
            raise ValueError("Parameter is marked as invalid, but has a valid value.")
        case IntFieldError.EMPTY.name:
            return _expect_error_message(test_data, "task file header", stdout)
        case IntFieldError.STRING.name:
            return _expect_error_message(test_data, "task file header", stdout)
        case IntFieldError.MINUS_1.name:
            return _expect_error_message(test_data, "number of tasks", stdout)
        case IntFieldError.PLUS_1.name:
            return _expect_error_message(test_data, "number of tasks", stdout)
        case _:
            _raise_unimplemented(test_data)


def _evaluate_hostname(test_data: AcquisitionTestCase, stdout: str) -> OracleResult:
    value = test_data.parameters.connection_hostname

    match value:
        case parameter_spec.INVALID_HOSTNAME | "":
            return _expect_error_message(
                test_data, "Could not resolve hostname", stdout
            )
        case None:
            return _expect_error_message(
                test_data, "Missing entry in connection parameters", stdout
            )
        case _:
            _raise_unimplemented(test_data)


def _evaluate_port(test_data: AcquisitionTestCase, stdout: str, stderr: str) -> OracleResult:
    """Bad port number"""
    value = test_data.parameters.connection_port
    if value is None:
        # Port key absent from JSON; paramiko defaults to 22.
        # What we expect depends on what's actually running on port 22.
        if port22_status == Port22Status.SSH_AUTH_REQUIRED:
            expected_error_msg = "Authentication failed"
        elif port22_status == Port22Status.NON_SSH:
            expected_error_msg = "Could not establish an SSH session"
        else:  # CLOSED: connection refused or timeout
            expected_error_msg = "Could not reach the server"

    elif not isinstance(value, int) or isinstance(value, bool):
        expected_error_msg = "Port number should be an integer"
    elif not (1 <= value <= 65535):
        expected_error_msg = "not in valid range"
    else:
        # Valid range but nothing listening on this port in the test environment
        expected_error_msg = "Could not reach the server"
    return _expect_error_message(test_data, expected_error_msg, stdout)


def _evaluate_password(test_data: AcquisitionTestCase, stdout: str) -> OracleResult:
    value = test_data.parameters.connection_password

    match value:
        case parameter_spec.INVALID_PASSWORD:
            return _expect_error_message(test_data, "Authentication failed", stdout)
        case None:
            return _expect_error_message(
                test_data, "Missing entry in connection parameters", stdout
            )
        case _:
            _raise_unimplemented(test_data)


def _evaluate_emulator_behavior(test_data: AcquisitionTestCase, stdout: str, stderr: str) -> OracleResult:
    try:
        behavior: TerrameterBehavior = TerrameterBehavior[str(test_data["emulator_behavior"])]
    except KeyError:
        raise NotImplementedError(f"Terrameter behavior {test_data["emulator_behavior"]!r} not ")
    error_message = _find_stdout_error_message(stdout)
    
    match behavior:
        #case TerrameterBehavior.DROPPED_MESSAGES: 
        #    return _expect_error_message(test_data, "A connection error occured", stdout, allow_without_error=True)
        #case TerrameterBehavior.RESTART_DURING_MEASUREMENT:
        #    return _expect_error_message(test_data, "A connection error occured", stdout, allow_without_error=True)
        #case TerrameterBehavior.DELETE_PROJECT_BEFORE_TRANSFER:
        #    return _expect_error_message(test_data, "Failed to transfer project", stdout)
        #case TerrameterBehavior.TIMEOUT:
        #    return _expect_error_message(test_data, "A connection error occured", stdout)
        case _:
            _raise_unimplemented(test_data)

def _evaluate_task_property(test_case: AcquisitionTestCase, file: int, task: int, property: str, stdout: str) -> OracleResult:
    """Any invalid property of a task"""
    parameter_name = f"taskfile{file}_task{task}_{property}"
    parameter_value = test_case.parameters[parameter_name]

    if parameter_value == "" or str(parameter_value).startswith("#"):
        return _expect_error_message(test_case, "missing row", stdout)

    match property:
        case "name":
            return _expect_error_message(test_case, "task name", stdout)
        case "settings":
            return _expect_error_message(test_case, "task settings", stdout)
        case "spread":
            return _expect_error_message(test_case, "task spread", stdout)
        case "protocol":
            return _expect_error_message(test_case, "protocol file", stdout)
        case "spacing":
            return _expect_error_message(test_case, "spacing", stdout)
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
        case "num_args":
            return _expect_error_message(test_data, "No task file given", stdout)
        case "arg_taskfile1" | "arg_taskfile2":
            return _evaluate_arg_task_files(test_data, stdout)
        case "connection_hostname":
            return _evaluate_hostname(test_data, stdout)
        case "connection_port":
            return _evaluate_port(test_data, stdout, stderr)
        case "connection_password":
            return _evaluate_password(test_data, stdout)
        case p if (match := re.match(RE_TASK, p)) is not None:
            file = int(match.group("file"))
            task = int(match.group("task"))
            property = str(match.group("property"))
            return _evaluate_task_property(test_data, file, task, property, stdout)
        case "emulator_behavior":
            return _evaluate_emulator_behavior(test_data, stdout, stderr)
        case "taskfile1_number_of_tasks_error" | "taskfile2_number_of_tasks_error":
            return _evaluate_number_of_tasks_error(test_data, stdout, stderr)
        case _:
            if (msg := _find_stdout_error_message(stdout)) is not None:
                _logging.warning(
                    f"No specific evaluator exists for invalid parameter {invalid_parameter}. Assuming this is the expected error: {msg}"
                )
                return OracleResult(True)
            _raise_unimplemented(test_data)

if __name__ == "__main__":
    print(OracleResult(False, "Message"))
    print((OracleResult(False, "Message").frame or FrameType()))