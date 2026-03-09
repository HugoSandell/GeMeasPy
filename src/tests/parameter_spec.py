from typing import TypeAlias
import itertools
import enum

from tests.terrameter_model.behaviours import TerrameterBehaviour

ParameterSpec: TypeAlias = dict[str, list[str | int | bool | None | list[str | int | bool | None] | TerrameterBehaviour]]

ABSENT = ""
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
INVALID_HOSTNAME = "&%¤(#"

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
    "emulator_behaviour": [*TerrameterBehaviour]
}

# Add tasks programatically
for file, taskid in [itertools.permutations(range(1,3))]:
    PARAM_SPEC[f"taskfile{file}_task{taskid}_name"] = ["", f"Task{taskid}", "#TaskX"]
    PARAM_SPEC[f"taskfile{file}_task{taskid}_spread"] = ["", INVALID_FILE, VALID_SPREADFILE]
    PARAM_SPEC[f"taskfile{file}_task{taskid}_protocol"] = ["", INVALID_FILE, VALID_PROTOCOLFILE]
    PARAM_SPEC[f"taskfile{file}_task{taskid}_settings"] = ["", INVALID_FILE, VALID_SETTINGSFILE]
    PARAM_SPEC[f"taskfile{file}_task{taskid}_spacing"] = ["", "1 1 1", "1 1 1 1", "I I I"]