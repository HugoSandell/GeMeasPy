from dataclasses import dataclass, field
from typing import Any, Iterator
from types import NoneType

from tests.parameters import ParameterValue
from tests.test_case import AcquisitionTestCase, TestCase
from tests.terrameter_model.behaviours import TerrameterBehaviour

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


@dataclass
class ParameterSpec:
    TestCaseType: type = TestCase

    def __iter__(self) -> Iterator[str]:
        return iter(filter(lambda key: key != "TestCaseType", vars(self))) # _TestCaseType is a metavariable
    
    def __setitem__(self, name: str, value: list[ParameterValue]) -> None:
        if name not in vars(self):
            raise KeyError(f"{self.__class__.__name__} has no attribute '{name}'")
        self.__setattr__(name, value)
        
    def __getitem__(self, name: str) -> list[ParameterValue]:
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
        if not any(value == known_good_value for known_good_value in self[name]):
            return ValueError(f"Parameter value {repr(value)} is invalid for parameter '{name}'")
        return None

@dataclass
class AcquisitionParameterSpec(ParameterSpec):
    TestCaseType: type = AcquisitionTestCase
    
    arg_task_files: list[list[str]] = field(default_factory=lambda:[
        [], 
        [""], 
        [INVALID_FILE], 
        [VALID_TASKFILE1], 
        [INVALID_FILE, VALID_TASKFILE1], 
        [VALID_TASKFILE1, INVALID_FILE], 
        [VALID_TASKFILE1, VALID_TASKFILE2]
    ])
    # Task file headers
    taskfile1_number_of_tasks: list[str] = field(default_factory=lambda:[
        "",
        "0",
        "1",
        "2",
        "X",
    ])
    taskfile1_relay_type: list[str] = field(default_factory=lambda:[
        "",
        "0"
    ])
    taskfile2_number_of_tasks: list[str] = field(default_factory=lambda:[
        "",
        "0",
        "1",
        "2",
        "X",
    ])
    taskfile2_relay_type: list[str] = field(default_factory=lambda:[
        "",
        "0"
    ])
    # config.py
    config_projects_folder: list[str] = field(default_factory=lambda:[INVALID_FILE, VALID_PROJECTS_FOLDER])
    config_local_data_path: list[str] = field(default_factory=lambda:[INVALID_FILE, VALID_LOCAL_DATA_PATH])
    config_connection_file: list[str] = field(default_factory=lambda:[INVALID_FILE, VALID_CONNECTION_FILE]) 
    # connection_settings.json
    connection_hostname: list[str | None] = field(
        default_factory=lambda: ["", VALID_HOSTNAME, INVALID_HOSTNAME, None]
    )
    connection_port: list[str | int | None] = field(
        default_factory=lambda: ["", VALID_PORT, 0, -1, 65536, None]
    )
    connection_password: list[str | None] = field(
        default_factory=lambda: ["", INVALID_PASSWORD, None]
    )
    # emulator
    emulator_behaviour: list[str] = field(default_factory=lambda:[b.name for b in TerrameterBehaviour])
    
    taskfile1_task1_name: list[str] = field(default_factory=lambda:["", f"Task1", "#TaskX"])
    taskfile1_task1_spread: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_SPREADFILE])
    taskfile1_task1_protocol: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_PROTOCOLFILE])
    taskfile1_task1_settings: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_SETTINGSFILE])
    taskfile1_task1_spacing: list[str] = field(default_factory=lambda:["", "1 1 1", "1 1 1 1", "I I I"])
    
    taskfile1_task2_name: list[str] = field(default_factory=lambda:["", f"Task2", "#TaskX"])
    taskfile1_task2_spread: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_SPREADFILE])
    taskfile1_task2_protocol: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_PROTOCOLFILE])
    taskfile1_task2_settings: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_SETTINGSFILE])
    taskfile1_task2_spacing: list[str] = field(default_factory=lambda:["", "1 1 1", "1 1 1 1", "I I I"])
    
    taskfile2_task1_name: list[str] = field(default_factory=lambda:["", f"Task1", "#TaskX"])
    taskfile2_task1_spread: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_SPREADFILE])
    taskfile2_task1_protocol: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_PROTOCOLFILE])
    taskfile2_task1_settings: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_SETTINGSFILE])
    taskfile2_task1_spacing: list[str] = field(default_factory=lambda:["", "1 1 1", "1 1 1 1", "I I I"])
    
    taskfile2_task2_name: list[str] = field(default_factory=lambda:["", f"Task2", "#TaskX"])
    taskfile2_task2_spread: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_SPREADFILE])
    taskfile2_task2_protocol: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_PROTOCOLFILE])
    taskfile2_task2_settings: list[str] = field(default_factory=lambda:["", INVALID_FILE, VALID_SETTINGSFILE])
    taskfile2_task2_spacing: list[str] = field(default_factory=lambda:["", "1 1 1", "1 1 1 1", "I I I"])

@dataclass
class Constraint:
    text: str = ""
    parameters: list[str] = field(default_factory=list)


# TODO: Roll constraints into parameter spec?
ACQUISITION_CONSTRAINTS: list[Constraint] = [
    Constraint("", []),
]
ACQUISITION_PARAM_SPEC = AcquisitionParameterSpec()