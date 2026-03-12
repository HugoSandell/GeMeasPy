from dataclasses import dataclass, field
import typing
from collections.abc import Iterator

from gemeaspy.tests.parameters import ParameterValue


class TestCase:
    def __iter__(self) -> Iterator[str]:
        return iter(vars(self))
    def __setitem__(self, name: str, value: ParameterValue) -> None:
        if name not in vars(self):
            raise KeyError(f"{self.__class__.__name__} has no attribute '{name}'")
        self.__dict__[name] = value
    def __getitem__(self, name: str = "") -> ParameterValue:
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
class AcquisitionTestCase(TestCase):
    arg_task_files: list[str] = field(default_factory=list)
    # Task file headers
    taskfile1_number_of_tasks: str = ""
    taskfile1_relay_type: str = ""
    taskfile2_number_of_tasks: str = ""
    taskfile2_relay_type: str = ""
    # config.py
    config_projects_folder: str = ""
    config_local_data_path: str = ""
    config_connection_file: str = ""
    # connection_settings.json
    connection_hostname: str | None = None
    connection_port: int | str | None = None
    connection_password: str | None = None
    # emulator
    emulator_behaviour: str = ""
    
    taskfile1_task1_name: str = ""
    taskfile1_task1_spread: str = ""
    taskfile1_task1_protocol: str = ""
    taskfile1_task1_settings: str = ""
    taskfile1_task1_spacing: str = ""
    
    taskfile1_task2_name: str = ""
    taskfile1_task2_spread: str = ""
    taskfile1_task2_protocol: str = ""
    taskfile1_task2_settings: str = ""
    taskfile1_task2_spacing: str = ""
    
    taskfile2_task1_name: str = ""
    taskfile2_task1_spread: str = ""
    taskfile2_task1_protocol: str = ""
    taskfile2_task1_settings: str = ""
    taskfile2_task1_spacing: str = ""
    
    taskfile2_task2_name: str = ""
    taskfile2_task2_spread: str = ""
    taskfile2_task2_protocol: str = ""
    taskfile2_task2_settings: str = ""
    taskfile2_task2_spacing: str = ""