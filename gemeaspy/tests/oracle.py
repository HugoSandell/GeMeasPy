"""This module is responsible for reviewing test execution data and determining whether or not a failure has occurred"""

import inspect
import os
import re
import stat
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path, PurePosixPath
from types import FrameType
from typing import NoReturn

from gemeaspy.settings import config
from gemeaspy.tests import _logging
from gemeaspy.tests.generator import parameter_spec
from gemeaspy.tests.generator.int_field_error import IntFieldError
from gemeaspy.tests.generator.parameter_spec import (
    INVALID_FILE,
    AcquisitionParameterSpec,
)
from gemeaspy.tests.generator.test_case import AcquisitionTestCase, TestCase
from gemeaspy.tests.setup_config import ConfigState
from gemeaspy.tests.terrameter_model.database import ProjectDatabase
from gemeaspy.tests.terrameter_model.parameters import TerrameterMisbehavior
from gemeaspy.tests.terrameter_model.terrameter import TerrameterLS


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
_RE_RELAY_TYPE = re.compile(r"taskfile(?P<file>\d+)_relay_type$")
_RE_TASK_PROPERTY = re.compile(
    r"taskfile(?P<file>\d+)_task(?P<task>\d+)_"
    r"(?P<property>spread|protocol|name|settings|spacing)$"
)


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

def _expect_error_message(test_case: TestCase, expected_error: str | Sequence[str], stdout: str, allow_without_error = False) -> OracleResult:
    """Evaluate stdout, expecting an error message and return an OracleResult accordingly."""
    param_name = test_case.invalid_parameter
    param_value = test_case[str(param_name)]
    if isinstance(expected_error, str):
        expected_error = (expected_error,)
    error_message = _find_stdout_error_message(stdout)
    if error_message is None:
        if allow_without_error:
            return OracleResult(True, context=1)
    if error_message is not None and any(e.lower() in error_message.lower() for e in expected_error):
        return OracleResult(True, context=1)
    else:
        expected_error_formatted = ' or '.join([repr(e) for e in expected_error])
        _logging.info(f"Expected {expected_error_formatted} in stdout, got:\n{stdout}")
        return OracleResult(False, f"Did not find error message containing {expected_error_formatted} in output for invalid parameter {param_name} = {param_value!r}.", context=1)


def _expected_projects(test_data: AcquisitionTestCase) -> list[int]:
    projects = []
    if test_data.parameters.num_args > 0:
        if test_data.parameters.taskfile1_number_of_tasks > 0:
            projects.append(1)
    if test_data.parameters.num_args > 1:
        if test_data.parameters.taskfile2_number_of_tasks > 0:
            projects.append(2)
    return projects


def _evaluate_transfer_valid(test_data: AcquisitionTestCase, config_state: ConfigState, emulator: TerrameterLS) -> OracleResult:
    """Checks whether the project has been transferred correctly"""
    EXPECTED_PROJECT_FILES = ["project.db", "project_name.txt"] # Check for these, relative to project directory
    local_project_path = Path(config.LOCAL_PATH_TO_DATA)
    terrameter_project_path = test_data.parameters.config_projects_folder

    def collect_files(remote_dir: str) -> dict[PurePosixPath, bytes]:
        """Recursively collect {relative_path: content} for all files under remote_dir"""
        result: dict[PurePosixPath, bytes] = {}

        def is_dir(f: str) -> bool:
            state_mode = emulator.stat(f, remote_dir).st_mode
            return stat.S_ISDIR(state_mode)

        try:
            project_dirs = filter(is_dir, emulator.list_folder(remote_dir))
        except FileNotFoundError:
            return {}
                
        for project_dir in project_dirs:
            for project_file in EXPECTED_PROJECT_FILES:    
                relative_path = PurePosixPath(project_dir, project_file)
                data = emulator.read_file(str(relative_path), remote_dir)
                result[relative_path] = data
        return result

    # Allow projects to be removed or kept. The /removed path is used to keep backups of removed files
    removed_project_path = PurePosixPath("/", "removed", terrameter_project_path.lstrip("/")).as_posix()
    terrameter_files = {
        **collect_files(terrameter_project_path),
        **collect_files(removed_project_path),
    }

    expected_num_projects = len(_expected_projects(test_data))
    expected_num_project_files = expected_num_projects * len(EXPECTED_PROJECT_FILES)
    if len(terrameter_files) != expected_num_project_files:
        return OracleResult(False, f"Expected {expected_num_project_files} project files to be transferred, but found {len(terrameter_files)}")
    if len(terrameter_files) <= 0 and expected_num_projects > 0:
        return OracleResult(False, "Could not find any project files on Terrameter emulator")

    for rel_path, expected_data in terrameter_files.items():
        parts = rel_path.parts
        for i in range(1, len(parts)):
            ancestor = os.path.join(local_project_path, *parts[:i])
            if not os.path.isdir(ancestor):
                return OracleResult(False, f"Directory that should have been transferred not found locally: {os.path.join(*parts[:i])!r}")
        local_file = os.path.join(local_project_path, *parts)
        if not os.path.isfile(local_file):
            return OracleResult(False, f"Project file that should have been transferred was not found locally: {rel_path!r}")
        with open(local_file, "rb") as f:
            actual_data = f.read()
        if actual_data != expected_data:
            return OracleResult(False, f"Content mismatch for transferred file: {rel_path!r}")

    return OracleResult(True)

def _evaluate_emulator_valid(test_data: AcquisitionTestCase, 
                             emulator: TerrameterLS) -> OracleResult:
    """Checks whether emulator state is ok"""
    for project_name in emulator._projects:
        is_project_name_suffixed = not project_name.endswith(("_1", "_2"))
        if test_data.parameters.emulator_suffix_project_name and is_project_name_suffixed:
            emulator._projects[project_name].name
            return OracleResult(
                False, 
                "Test case was configured to add '_#' suffix " + 
                f"to all projects, but {project_name!r} does " + 
                "not have a suffix _1 or_2."
            )

    expected_projects = _expected_projects(test_data)

    # Verify number of projects
    num_projects = len(emulator._projects)
    if num_projects != len(expected_projects):
        return OracleResult(
            False,
            f"Expected {len(expected_projects)} projects to be created on emulator, but found {num_projects}",
        )
    if num_projects == 0:
        return OracleResult(True)

    # Verify project states
    project_names = sorted(emulator._projects)

    def _evaluate_project(project_idx: int, project_no: int) -> OracleResult:
        project_name = project_names[project_idx]
        project = emulator._projects[project_name]

        # Verify number of tasks
        expected_tasks = test_data.parameters[f"taskfile{project_no}_number_of_tasks"]
        assert type(expected_tasks) is int
        if len(project.tasks) != expected_tasks:
            return OracleResult(
                False,
                f"Expected {expected_tasks} tasks to be created for taskfile {project_no}, but found {len(project.tasks)}",
            )

        # Verify tasks in database
        db_path = PurePosixPath(
            test_data.parameters.config_projects_folder, project_name, "project.db"
        )
        try:
            db_file = emulator.open_file(str(db_path))
        except FileNotFoundError:
            db_path = PurePosixPath("/removed", db_path.relative_to("/"))
            db_file = emulator.open_file(str(db_path))
        db = ProjectDatabase(db_file)
        task_rows = db.tasks()
        if len(task_rows) != expected_tasks:
            return OracleResult(
                False,
                f"Expected {expected_tasks} task rows in project {project_no} database, but found {len(task_rows)}",
            )
        for task_i in range(expected_tasks):
            actual_name = task_rows[task_i].Name
            expected_prefix = (
                parameter_spec.valid_task_name(project_no, task_i + 1) + "_"
            )
            if not actual_name.startswith(expected_prefix):
                return OracleResult(
                    False,
                    f"Expected task name starting with {expected_prefix} in database, but found {actual_name}",
                )

        return OracleResult(True)

    for project_idx, project_no in enumerate(expected_projects):
        if not (result := _evaluate_project(project_idx, project_no)):
            return result

    return OracleResult(True)

# Evaluators
def _evaluate_any(config_state: ConfigState) -> OracleResult:
    """Checks properties that should hold for all cases"""
    if config_state.data_invalid_is_modified():
        return OracleResult(False, "SUT modified file configured as LOCAL_PATH_TO_DATA")
    return OracleResult(True)

def _evaluate_valid(test_data: AcquisitionTestCase, stdout: str, stderr:str, config_state: ConfigState, emulator: TerrameterLS) -> OracleResult:
    """Checks that results are consistent with valid inputs"""
    # Find any faulty states
    err_pos = stdout.find("Error: ")
    if err_pos >= 0:
        _logging.info(f"SUT failed with stdout:\n{stdout}\nstderr:\n{stderr}")
        return OracleResult(False, stdout[err_pos:].splitlines()[0])
    
    # Check transferred files - do the transferred project files match those on the emulator? 
    if not (transfer_check_result := _evaluate_transfer_valid(test_data, config_state, emulator)):
        return transfer_check_result
    # Check transferred files - do the transferred project files match those on the emulator? 
    if not (transfer_check_result := _evaluate_emulator_valid(test_data, emulator)):
        return transfer_check_result
    
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
        case IntFieldError.CORRECT:
            raise ValueError("Parameter is marked as invalid, but has a valid value.")
        case IntFieldError.EMPTY:
            return _expect_error_message(test_data, "task file header", stdout)
        case IntFieldError.STRING:
            return _expect_error_message(test_data, "task file header", stdout)
        case IntFieldError.MINUS_1:
            return _expect_error_message(test_data, "number of tasks", stdout)
        case IntFieldError.PLUS_1:
            return _expect_error_message(test_data, "number of tasks", stdout)
        case _:
            _raise_unimplemented(test_data)


def _evaluate_relay_type(
    test_data: AcquisitionTestCase, file: int, stdout: str
) -> OracleResult:
    value = test_data[f"taskfile{file}_relay_type"]

    match value:
        case "":
            return _expect_error_message(test_data, "task file header", stdout)
        case _:
            _raise_unimplemented(test_data)


def _evaluate_hostname(test_data: AcquisitionTestCase, stdout: str) -> OracleResult:
    value = test_data.parameters.connection_hostname

    match value:
        case parameter_spec.INVALID_HOSTNAME | "":
            return _expect_error_message(
                test_data, "hostname", stdout
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
        if port22_status in (Port22Status.SSH_AUTH_REQUIRED, Port22Status.NON_SSH):
            expected_error_msg = ["Authentication failed", "Could not establish an SSH session"]
        else:  # CLOSED: connection refused or timeout
            expected_error_msg = ["Could not reach the server", "Connection timed out"]

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


def _evaluate_emulator_misbehavior(
    test_data: AcquisitionTestCase, stdout: str, stderr: str
) -> OracleResult:
    try:
        misbehavior: TerrameterMisbehavior = TerrameterMisbehavior[
            str(test_data["emulator_misbehavior"])
        ]
    except KeyError:
        raise NotImplementedError(
            f"Terrameter misbehavior {test_data['emulator_misbehavior']!r} not "
        )
    error_message = _find_stdout_error_message(stdout)

    match misbehavior:
        # case TerrameterMisbehavior.DROPPED_MESSAGES:
        #     return _expect_error_message(test_data, "A connection error occured", stdout, allow_without_error=True)
        # case TerrameterMisbehavior.RESTART_DURING_MEASUREMENT:
        #     return _expect_error_message(test_data, "A connection error occured", stdout, allow_without_error=True)
        # case TerrameterMisbehavior.DELETE_PROJECT_BEFORE_TRANSFER:
        #     return _expect_error_message(test_data, "Failed to transfer project", stdout)
        # case TerrameterMisbehavior.TIMEOUT:
        #     return _expect_error_message(test_data, "A connection error occured", stdout)
        case _:
            _raise_unimplemented(test_data)

def _evaluate_task_property(test_case: AcquisitionTestCase, file: int, task: int, property: str, stdout: str) -> OracleResult:
    """Any invalid property of a task"""
    parameter_name = f"taskfile{file}_task{task}_{property}"
    parameter_value = test_case.parameters[parameter_name]

    if parameter_value == "" or str(parameter_value).startswith("#"):
        return _expect_error_message(test_case, "Failed to parse task file", stdout)

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
    emulator: TerrameterLS,
) -> OracleResult:
    result = _evaluate_any(config_state)
    if not result:
        return result

    param_spec = AcquisitionParameterSpec()
    invalid_parameter = test_data.invalid_parameter

    match invalid_parameter:
        case None:
            return _evaluate_valid(test_data, stdout, stderr, config_state, emulator)
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
        case p if (match := re.match(_RE_TASK_PROPERTY, p)) is not None:
            file = int(match.group("file"))
            task = int(match.group("task"))
            property = str(match.group("property"))
            return _evaluate_task_property(test_data, file, task, property, stdout)
        case "emulator_misbehavior":
            return _evaluate_emulator_misbehavior(test_data, stdout, stderr)
        case "taskfile1_number_of_tasks_error" | "taskfile2_number_of_tasks_error":
            return _evaluate_number_of_tasks_error(test_data, stdout, stderr)
        case p if m := _RE_RELAY_TYPE.match(p):
            file = int(m.group("file"))
            return _evaluate_relay_type(test_data, file, stdout)
        case "config_local_data_path":
            return _expect_error_message(test_data, "local data directory", stdout)
        case "config_projects_folder":
            num_tasks = test_data.parameters.taskfile1_number_of_tasks 
            if test_data.parameters.num_args > 1:
                num_tasks += test_data.parameters.taskfile2_number_of_tasks 
            if num_tasks > 0:
                return _expect_error_message(test_data, ("transfer failed", "projects folder", "project transfer"), stdout)
            else:
                return OracleResult(True) # TODO: This would be best implemented as a constraint
        case "config_connection_file":
            return _expect_error_message(
                test_data, "Terrameter connection settings file", stdout
            )
        case _:
            if (msg := _find_stdout_error_message(stdout)) is not None:
                _logging.warning(
                    f"No specific evaluator exists for invalid parameter {invalid_parameter}. Got the following error: {msg!r}"
                )
            else:
                _logging.warning(
                    f"No specific evaluator exists for invalid parameter {invalid_parameter}."
                )
            _raise_unimplemented(test_data)

if __name__ == "__main__":
    print(OracleResult(False, "Message"))
    print((OracleResult(False, "Message").frame or FrameType()))