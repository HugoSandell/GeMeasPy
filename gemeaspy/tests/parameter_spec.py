"""Specification for parameter names and values. Used as input for test generation."""
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeAlias, TypeVar
from types import NoneType

from gemeaspy.tests.parameters import ParameterValue
from gemeaspy.tests.test_case import AcquisitionTestCase, TestCase
from gemeaspy.tests.terrameter_model.behaviours import TerrameterBehaviour

INVALID_FILE = "__INVALID_FILE__"  # A path to a file that doesn't exist neither locally nor remotely
VALID_TASKFILE1 = "__VALID_TASKFILE1__"
VALID_TASKFILE2 = "__VALID_TASKFILE2__"
VALID_SPREADFILE = "2X21.xml"
VALID_PROTOCOLFILE = "Gradient_2x21.xml"
VALID_SETTINGSFILE = "testing1s.settings"

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
    if type(valid) != list or (invalid != None and type(invalid) != list):
        raise TypeError(f"Arguments must be lists! Got {type(valid)}, {type(invalid)}")
    return field(default_factory=lambda: (valid, invalid if invalid else []))

@dataclass
class ParameterSpec:
    TestCaseType: type = TestCase

    def __iter__(self) -> Iterator[str]:
        return iter(filter(lambda key: key != "TestCaseType", vars(self))) # _TestCaseType is a metavariable
    
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
    TestCaseType: type = AcquisitionTestCase
    
    arg_task_files: ParamSpecEntry[list[str]] = param_values([
            [VALID_TASKFILE1],
            [VALID_TASKFILE1, VALID_TASKFILE2]
        ],[
            [], 
            [INVALID_FILE], 
            [INVALID_FILE, VALID_TASKFILE1], 
            [VALID_TASKFILE1, INVALID_FILE]
        ]
    )
    # Task file headers
    taskfile1_number_of_tasks: ParamSpecEntry[int] = param_values([
        0,
        1,
        2,
    ])
    taskfile1_number_of_tasks_error: ParamSpecEntry[int] = param_values([0], [-1, +1])
    """The error of the number of tasks count. 0 - No error"""
    taskfile1_relay_type: ParamSpecEntry[str] = param_values(["", "0"])
    taskfile2_number_of_tasks: ParamSpecEntry[int] = param_values([
        0,
        1,
        2,
    ])
    taskfile2_number_of_tasks_error: ParamSpecEntry[int] = param_values([0], [-1, +1])
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
    emulator_behaviour: ParamSpecEntry[str] = field(
        default_factory=lambda:
            (
                [TerrameterBehaviour.IDEAL.name], 
                [b.name for b in TerrameterBehaviour if b is not TerrameterBehaviour.IDEAL]
            )
        )
    
    # Tasks 
    #  Empty "" is valid because it should be used for absent tasks when the 
    #  task file header specifies fewer tasks. Its use should be controlled 
    #  with constraints
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

@dataclass
class Constraint:
    text: str = ""
    parameters: list[str] = field(default_factory=list)
    def __str__(self) -> str:
        return self.text


ACQUISITION_PARAM_SPEC = AcquisitionParameterSpec()

def constraints_for_empty_task(N_param: str, element: str, element_index: int) -> list[Constraint]:
    """Generate the constraints dictating when a task's valid parameter values should be \"\""""
    # TODO: These constraints slow down generation considerably. Are there alternatives?
    # Could we manually apply N < element_index => param == "" after running ACTS, and remove duplicates?
    
    constraints: list[Constraint] = []
    suffixes = ("_name", "_spread", "_protocol", "_settings", "_spacing")
    
    antecedent = f"{N_param} < {element_index}"
    for element_suffix in suffixes:
        parameter_name = element + element_suffix
        parameter_base_case = ACQUISITION_PARAM_SPEC[parameter_name][0][0]
        if type(parameter_base_case) == str:
            parameter_base_case = f'"{parameter_base_case}"'
        consequent = f" => {parameter_name} == {parameter_base_case}"
        constraints.append(
            Constraint(antecedent + consequent, [N_param, parameter_name])
        )
    return constraints

# TODO: Roll constraints into parameter spec?
ACQUISITION_CONSTRAINTS: list[Constraint] = [
    *constraints_for_empty_task("taskfile1_number_of_tasks", "taskfile1_task1", 1),
    *constraints_for_empty_task("taskfile1_number_of_tasks", "taskfile1_task2", 2),
    *constraints_for_empty_task("taskfile2_number_of_tasks", "taskfile2_task1", 1),
    *constraints_for_empty_task("taskfile2_number_of_tasks", "taskfile2_task2", 2),
]

if __name__=="__main__":
    N_param = "N"
    print(f"Generated constraints limit value to base case depending on {N_param}\n")

    for element_index in (1, 2, 4):
        element = "E" + str(element_index)
        print(f"Constraints for element #{element_index} ({element}) in a collection of {N_param} elements:")
        for constraint in constraints_for_empty_task(N_param, element, element_index):
            print(constraint)
    
    