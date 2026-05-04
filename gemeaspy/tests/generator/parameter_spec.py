"""Specification for parameter names and values. Used as input for test generation."""

from collections.abc import Generator, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from types import NoneType
from typing import Any, TypeAlias, TypeVar

from gemeaspy.tests.generator.constraint import Constraint
from gemeaspy.tests.generator.int_field_error import IntFieldError
from gemeaspy.tests.generator.parameters import ParameterValue
from gemeaspy.tests.generator.test_case import (
    AcquisitionTestCase,
    AcquisitionTestCaseParameters,
    TestCase,
)
from gemeaspy.tests.generator.util import obj2acts
from gemeaspy.tests.terrameter_model.parameters import (
    TerrameterMisbehavior,
    TerrameterProjectState,
)

INVALID_FILE = "__INVALID_FILE__"  # A path to a file that doesn't exist neither locally nor remotely
VALID_TASKFILE1 = "__VALID_TASKFILE1__"
VALID_TASKFILE2 = "__VALID_TASKFILE2__"
VALID_SPREADFILE = "2X21.xml"
VALID_PROTOCOLFILE = "DipoleDipole2x21.xml"
VALID_SETTINGSFILE = "CABIN.settings"

VALID_PROJECTS_FOLDER = "/media/mmcblk0p1/projects"
VALID_LOCAL_DATA_PATH = "__VALID_LOCAL_DATA_PATH__"
VALID_CONNECTION_FILE = "__VALID_CONNECTION_FILE__"

VALID_HOSTNAME = "127.0.0.1"
INVALID_HOSTNAME = "__INVALID_HOSTNAME__"
VALID_PORT = "__VALID_PORT__"
INVALID_PASSWORD = "__INVALID_PASSWORD__"

T = TypeVar('T', bound = ParameterValue)
ParamSpecEntry: TypeAlias = tuple[list[T], list[T]]
"""A pair of lists, the first of valid values and the second of invalid values."""

def param_values[T](valid: Sequence[T], invalid: Sequence[T] | None = None) -> ParamSpecEntry:
    if type(valid) != list or (isinstance(invalid, Sequence) and type(invalid) != list):
        raise TypeError(f"Arguments must be lists! Got {type(valid)}, {type(invalid)}")
    return field(default_factory=lambda: (valid, invalid if invalid else []))


def enum_param_values[T: StrEnum](enum: type[T], valid: Sequence[T]) -> ParamSpecEntry:
    return field(
        default_factory=lambda: (
            [enum(v.value) for v in valid],
            [enum(v.value) for v in enum if v not in valid],
        )
    )

@dataclass
class ParameterSpec:
    TestCaseType: type[TestCase] = TestCase

    def __iter__(self) -> Iterator[str]:
        return iter(filter(lambda key: key != "TestCaseType", vars(self))) # TestCaseType is a metavariable
    
    def __setitem__(self, name: str, value: ParamSpecEntry[ParameterValue]) -> None:
        if name not in vars(self):
            raise KeyError(f"{self.__class__.__name__} has no attribute '{name}'")
        self.__setattr__(name, value)
        
    def __getitem__(self, name: str) -> ParamSpecEntry[ParameterValue]:
        if name not in vars(self):
            raise KeyError(f"{self.__class__.__name__} has no attribute '{name}'")
        return vars(self)[name]
    
    def __len__(self) -> int:
        return len(vars(self)) - 1 # -1 for TestCaseType
    
    def __str__(self) -> str:
        return str(vars(self))
    
    def __repr__(self) -> str:
        return repr(vars(self))
    
    def validate_parameter(self, name: str, value: Any) -> NoneType | NameError | ValueError:
        """Return None iff the value is a valid ParameterValue, otherwise an Exception"""
        if name not in vars(self):
            return NameError(f"Parameter name '{name}' is invalid")
        if not any(value == known_good_value for known_good_value in self[name][0]+ self[name][1]):
            return ValueError(f"Parameter value {repr(value)} is invalid for parameter '{name}'")
        return None

@dataclass
class AcquisitionParameterSpec(ParameterSpec):
    TestCaseType: type[TestCase] = AcquisitionTestCase

    num_args: ParamSpecEntry[int] = param_values([1, 2], [0])    
    arg_taskfile1: ParamSpecEntry[str] = param_values([VALID_TASKFILE1],[INVALID_FILE])
    arg_taskfile2: ParamSpecEntry[str] = param_values([VALID_TASKFILE2],[INVALID_FILE])
    
    # Task file headers
    taskfile1_number_of_tasks: ParamSpecEntry[int] = param_values([
        0,
        1,
        2,
    ])
    taskfile1_number_of_tasks_error: ParamSpecEntry[IntFieldError] = enum_param_values(
        IntFieldError, [IntFieldError.CORRECT]
    )
    """The error of the number of tasks count. 0 - No error"""
    taskfile1_relay_type: ParamSpecEntry[str] = param_values(["0"], [""])
    taskfile2_number_of_tasks: ParamSpecEntry[int] = param_values([
        0,
        1,
        2,
    ])
    taskfile2_number_of_tasks_error: ParamSpecEntry[IntFieldError] = enum_param_values(
        IntFieldError, [IntFieldError.CORRECT]
    )
    """The error of the number of tasks count. 0 - No error"""
    taskfile2_relay_type: ParamSpecEntry[str] = param_values([
        "0"
    ], [""])
    # config.py
    config_projects_folder: ParamSpecEntry[str] = param_values([VALID_PROJECTS_FOLDER], [INVALID_FILE])
    config_local_data_path: ParamSpecEntry[str] = param_values([VALID_LOCAL_DATA_PATH], [INVALID_FILE])
    config_connection_file: ParamSpecEntry[str] = param_values([VALID_CONNECTION_FILE], [INVALID_FILE]) 
    # connection_settings.json
    connection_hostname: ParamSpecEntry[str | None] = param_values(
        valid = [VALID_HOSTNAME], invalid = ["", INVALID_HOSTNAME, None]
    )
    connection_port: ParamSpecEntry[str | int | None] = param_values(
        [VALID_PORT], invalid=["", 0, -1, 65536, None]
    )
    connection_password: ParamSpecEntry[str | None] = param_values(
        [""], [INVALID_PASSWORD, None]
    )
    
    # emulator
    emulator_misbehavior: ParamSpecEntry[str] = enum_param_values(
        TerrameterMisbehavior, [TerrameterMisbehavior.NONE]
    )
    emulator_project1_init_state: ParamSpecEntry[str] = enum_param_values(
        TerrameterProjectState, [TerrameterProjectState.UNINITIALISED, 
                                 TerrameterProjectState.INITIALISED, 
                                 TerrameterProjectState.OLD, 
                                 TerrameterProjectState.MEASURING,
                                 TerrameterProjectState.ONE_DONE, 
                                 TerrameterProjectState.ALL_DONE]
    )
    emulator_project2_init_state: ParamSpecEntry[str] = enum_param_values(
        TerrameterProjectState, [TerrameterProjectState.UNINITIALISED, 
                                 TerrameterProjectState.INITIALISED, 
                                 TerrameterProjectState.OLD, 
                                 TerrameterProjectState.MEASURING,
                                 TerrameterProjectState.ONE_DONE, 
                                 TerrameterProjectState.ALL_DONE]
    )

    # Tasks 
    taskfile1_task1_name: ParamSpecEntry[str] = param_values(
        ["Task1"], 
        ["#TaskX", ""]
        )
    taskfile1_task1_spread: ParamSpecEntry[str] = param_values(
        [VALID_SPREADFILE], [INVALID_FILE, ""]
    )
    taskfile1_task1_protocol: ParamSpecEntry[str] = param_values(
        [VALID_PROTOCOLFILE], [INVALID_FILE, ""]
    )
    taskfile1_task1_settings: ParamSpecEntry[str] = param_values(
        [VALID_SETTINGSFILE], [INVALID_FILE, ""]
    )
    taskfile1_task1_spacing: ParamSpecEntry[str] = param_values(
            ["1 1 1"],
            ["1 1 1 1", "I I I", ""]
        )
    
    taskfile1_task2_name: ParamSpecEntry[str] = param_values(
        ["Task2"], 
        ["#TaskX"]
        )
    taskfile1_task2_spread: ParamSpecEntry[str] = param_values(
        [VALID_SPREADFILE], [INVALID_FILE]
    )
    taskfile1_task2_protocol: ParamSpecEntry[str] = param_values(
        [VALID_PROTOCOLFILE], [INVALID_FILE]
    )
    taskfile1_task2_settings: ParamSpecEntry[str] = param_values(
        [VALID_SETTINGSFILE], [INVALID_FILE]
    )
    taskfile1_task2_spacing: ParamSpecEntry[str] = param_values(
            ["1 1 1"],
            ["1 1 1 1", "I I I"]
        )  

    taskfile2_task1_name: ParamSpecEntry[str] = param_values(
        ["Task1"], 
        ["#TaskX"]
        )
    taskfile2_task1_spread: ParamSpecEntry[str] = param_values(
        [VALID_SPREADFILE], [INVALID_FILE]
    )
    taskfile2_task1_protocol: ParamSpecEntry[str] = param_values(
        [VALID_PROTOCOLFILE], [INVALID_FILE]
    )
    taskfile2_task1_settings: ParamSpecEntry[str] = param_values(
        [VALID_SETTINGSFILE], [INVALID_FILE]
    )
    taskfile2_task1_spacing: ParamSpecEntry[str] = param_values(
            ["1 1 1"],
            ["1 1 1 1", "I I I"]
        )  
    
    taskfile2_task2_name: ParamSpecEntry[str] = param_values(
        ["Task2"], 
        []
        )
    taskfile2_task2_spread: ParamSpecEntry[str] = param_values([VALID_SPREADFILE], [])
    taskfile2_task2_protocol: ParamSpecEntry[str] = param_values(
        [VALID_PROTOCOLFILE], []
    )
    taskfile2_task2_settings: ParamSpecEntry[str] = param_values(
        [VALID_SETTINGSFILE], []
    )
    taskfile2_task2_spacing: ParamSpecEntry[str] = param_values(
            ["1 1 1"],
            []
        )  

class ACTSParameterType(Enum):
    NUM = "0"
    ENUM = "1"
    BOOLEAN = "2"

def acts_type(parameter_values: ParamSpecEntry | list[ParameterValue]) -> ACTSParameterType:
    """Determine the appropriate ACTS type for the given parameter"""
    if type(parameter_values) is tuple:
        parameter_values = [
            value for component in parameter_values for value in component
        ]
    if all(isinstance(v, bool) for v in parameter_values):
        return ACTSParameterType.BOOLEAN
    if all(isinstance(v, int) for v in parameter_values):
        return ACTSParameterType.NUM
    return ACTSParameterType.ENUM


ACQUISITION_PARAM_SPEC = AcquisitionParameterSpec()


def _base_case_constraints(
    antecedent: str, param_prefix: str, param_suffixes: Iterable[str]
) -> Generator[Constraint]:
    """Generate constraints restricting each parameter in a group to its first valid value"""
    for suffix in param_suffixes:
        parameter_name = f"{param_prefix}_{suffix}"
        parameter = ACQUISITION_PARAM_SPEC[parameter_name]
        parameter_base_case = obj2acts(parameter[0][0])
        if acts_type(parameter) == ACTSParameterType.ENUM:
            parameter_base_case = f'"{parameter_base_case}"'
        consequent = f" => {parameter_name} = {parameter_base_case}"
        yield Constraint(antecedent + consequent)


def _constraints_for_unused_taskfile(taskfile_no: int) -> Generator[Constraint]:
    return _base_case_constraints(
        f'num_args < {taskfile_no} || arg_taskfile{taskfile_no} = "{obj2acts(INVALID_FILE)}"',
        f"taskfile{taskfile_no}",
        ("number_of_tasks", "number_of_tasks_error", "relay_type"),
    )


def _constraints_for_unused_task(
    n_param: str, task_param_prefix: str, task_no: int
) -> Generator[Constraint]:
    """Generate the constraints dictating when a task's parameter values should be the base cases"""
    return _base_case_constraints(
        f"{n_param} < {task_no}",
        task_param_prefix,
        ("name", "spread", "protocol", "settings", "spacing"),
    )


# TODO: Roll constraints into parameter spec?
ACQUISITION_CONSTRAINTS: list[Constraint] = [
    Constraint(f'num_args < 1 => arg_taskfile1 = "{obj2acts(VALID_TASKFILE1)}"'),
    Constraint(f'num_args < 2 => arg_taskfile2 = "{obj2acts(VALID_TASKFILE2)}"'),
    *_constraints_for_unused_taskfile(1),
    *_constraints_for_unused_taskfile(2),
    *_constraints_for_unused_task("taskfile1_number_of_tasks", "taskfile1_task1", 1),
    *_constraints_for_unused_task("taskfile1_number_of_tasks", "taskfile1_task2", 2),
    *_constraints_for_unused_task("taskfile2_number_of_tasks", "taskfile2_task1", 1),
    *_constraints_for_unused_task("taskfile2_number_of_tasks", "taskfile2_task2", 2),
    Constraint(f'arg_taskfile1 != "{obj2acts(VALID_TASKFILE1)}" => emulator_project1_init_state = "{obj2acts(TerrameterProjectState.UNINITIALISED)}"'),
    Constraint(f'arg_taskfile2 != "{obj2acts(VALID_TASKFILE2)}" => emulator_project2_init_state = "{obj2acts(TerrameterProjectState.UNINITIALISED)}"'),
    Constraint(f'taskfile1_number_of_tasks < 1 => emulator_project1_init_state = "{obj2acts(TerrameterProjectState.UNINITIALISED)}"'),
    Constraint(f'taskfile2_number_of_tasks < 1 => emulator_project2_init_state = "{obj2acts(TerrameterProjectState.UNINITIALISED)}"'),
    Constraint(f'taskfile1_number_of_tasks = 1  => emulator_project1_init_state != "{obj2acts(TerrameterProjectState.ONE_DONE)}"'), # Because it is equivalent to all done
    Constraint(f'taskfile2_number_of_tasks = 1  => emulator_project2_init_state != "{obj2acts(TerrameterProjectState.ONE_DONE)}"'), # Because it is equivalent to all done
]

def _validate_spec():
    ignored_vars = ("TestCaseType", )
    acquisition_spec_vars = vars(AcquisitionParameterSpec())
    acquisition_case_vars = vars(AcquisitionTestCaseParameters())
    for p in acquisition_case_vars:
        if p in acquisition_spec_vars or p.startswith("__") or p in ignored_vars:
            continue
        raise AttributeError(f"Acquisition test case parameter {p!r} not found in parameter spec.")
    for p in acquisition_spec_vars:
        if p in acquisition_case_vars or p.startswith("__") or p in ignored_vars:
            continue
        raise AttributeError(f"Acquisition parameter spec entry {p!r} not found in test case spec.")

_validate_spec()

if __name__=="__main__":
    N_param = "N"
    print(f"Generated constraints limit value to base case depending on {N_param}\n")

    for element_index in (1, 2, 4):
        element = "E" + str(element_index)
        print(f"Constraints for element #{element_index} ({element}) in a collection of {N_param} elements:")
        for constraint in _constraints_for_unused_task(N_param, element, element_index):
            print(constraint)
