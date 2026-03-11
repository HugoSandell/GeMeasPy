from dataclasses import dataclass, field
from typing import Any, Iterator 
from types import NoneType

from tests.terrameter_model.behaviours import TerrameterBehaviour

type _ParameterBasicType = str | int | bool | NoneType
type ParameterValue = _ParameterBasicType | list[_ParameterBasicType]

INVALID_FILE = "N" # A path to a file that doesn't exist neither locally nor remotely
VALID_TASKFILE1 = "V1"
VALID_TASKFILE2 = "V2"
VALID_SPREADFILE = "V"
VALID_PROTOCOLFILE = "V"
VALID_SETTINGSFILE = "V"

VALID_PROJECTS_FOLDER = "V"
VALID_LOCAL_DATA_PATH = "V"
VALID_CONNECTION_FILE = "V"

VALID_HOSTNAME = "127.0.0.1"
INVALID_HOSTNAME = "bad.host.name"

@dataclass
class ParameterSpec:
    def __iter__(self) -> Iterator[str]:
        return iter(vars(self))
    def __setitem__(self, name: str, value: list[ParameterValue]) -> None:
        if name not in vars(self):
            raise KeyError(f"{self.__class__.__name__} has no attribute '{name}'")
        self.__setattr__(name, value)
    def __getitem__(self, name: str) -> list[ParameterValue]:
        if name not in vars(self):
            raise KeyError(f"{self.__class__.__name__} has no attribute '{name}'")
        return vars(self)[name]
    def __len__(self) -> int:
        return len(vars(self))
    def __str__(self) -> str:
        return str(vars(self))
    def __repr__(self) -> str:
        return repr(vars(self))

@dataclass
class AcquisitionParameterSpec(ParameterSpec):
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
    connection_hostname: list[str | None] = field(default_factory=lambda:["", VALID_HOSTNAME, INVALID_HOSTNAME, None])
    connection_port: list[str | int | None] = field(default_factory=lambda:["", 0, -1, 65536, None])
    connection_password: list[str | None] = field(default_factory=lambda:["", "X", None])
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


CONSTRAINTS: list[Constraint] = [
    Constraint("", []),
]

ACQUISITION_PARAM_SPEC = AcquisitionParameterSpec()

# Must be updated together if spec changes
def validate_parameter(name: str, value: Any) -> NoneType | NameError | ValueError:
    """Return None iff the value is a valid ParameterValue, otherwise an Exception"""
    if name not in vars(ACQUISITION_PARAM_SPEC):
        return NameError(f"Parameter name '{name}' is invalid")
    if not any(value == known_good_value for known_good_value in vars(ACQUISITION_PARAM_SPEC)[name]):
        return ValueError(f"Parameter value {repr(value)} is invalid for parameter '{name}'")
    return None