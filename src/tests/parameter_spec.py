from dataclasses import dataclass, field
from typing import Any
from types import NoneType

from tests.terrameter_model.behaviours import TerrameterBehaviour

type _ParameterBasicType = str | int | bool | NoneType
type ParameterValue = _ParameterBasicType | list[_ParameterBasicType]
type ParameterSpec = dict[str, list[ParameterValue]]

@dataclass
class Constraint:
    text: str = ""
    parameters: list[str] = field(default_factory=list)

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

CONSTRAINTS: list[Constraint] = [
    Constraint("", []),
]

PARAM_SPEC: ParameterSpec = {
    # CLI Arguments
    "arg_task_files": [
        [], 
        [""], 
        [INVALID_FILE], 
        [VALID_TASKFILE1], 
        [INVALID_FILE, VALID_TASKFILE1], 
        [VALID_TASKFILE1, INVALID_FILE], 
        [VALID_TASKFILE1, VALID_TASKFILE2]
    ], 
    # Task file headers
    "taskfile1_number_of_tasks": [
        "",
        "0",
        "1",
        "2",
        "X",
    ],
    "taskfile1_relay_type": [
        "",
        "0"
    ],
    "taskfile2_number_of_tasks": [
        "",
        "0",
        "1",
        "2",
        "X",
    ],
    "taskfile2_relay_type": [
        "",
        "0"
    ],
    # config.py
    "config_projects_folder": [INVALID_FILE, VALID_PROJECTS_FOLDER],
    "config_local_data_path": [INVALID_FILE, VALID_LOCAL_DATA_PATH],
    "config_connection_file": [INVALID_FILE, VALID_CONNECTION_FILE],
    # connection_settings.json
    "connection_hostname": ["", VALID_HOSTNAME, INVALID_HOSTNAME, None],
    "connection_port": ["", 0, -1, 65536, None],
    "connection_password": ["", "X", None],
    # emulator
    "emulator_behaviour": [b.name for b in TerrameterBehaviour]
}

# Add tasks programatically
for file, taskid in [(a, b) for a in range(1,3) for b in range(1,3)]:
    PARAM_SPEC[f"taskfile{file}_task{taskid}_name"] = ["", f"Task{taskid}", "#TaskX"]
    PARAM_SPEC[f"taskfile{file}_task{taskid}_spread"] = ["", INVALID_FILE, VALID_SPREADFILE]
    PARAM_SPEC[f"taskfile{file}_task{taskid}_protocol"] = ["", INVALID_FILE, VALID_PROTOCOLFILE]
    PARAM_SPEC[f"taskfile{file}_task{taskid}_settings"] = ["", INVALID_FILE, VALID_SETTINGSFILE]
    PARAM_SPEC[f"taskfile{file}_task{taskid}_spacing"] = ["", "1 1 1", "1 1 1 1", "I I I"]

# Must be updated together if spec changes
def validate_parameter(name: str, value: Any) -> NoneType | NameError | ValueError:
    """Return None iff the value is a valid ParameterValue, otherwise an Exception"""
    if name not in PARAM_SPEC:
        return NameError(f"Parameter name '{name}' is invalid")
    if not any(value == known_good_value for known_good_value in PARAM_SPEC[name]):
        return ValueError(f"Parameter value {repr(value)} is invalid for parameter '{name}'")
    return None