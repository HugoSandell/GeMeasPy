"""Definition of an individual test case."""
import typing
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from collections.abc import Iterator, Mapping

from gemeaspy.tests.generator.int_field_error import IntFieldError
from gemeaspy.tests.generator.parameters import ParameterValue
from gemeaspy.tests.terrameter_model.parameters import TerrameterProjectState

class TestCaseParameters(dict[str, ParameterValue]):
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
    def __contains__(self, key: object) -> bool:
        return key in vars(self)


@dataclass
class TestCase[T: TestCaseParameters](ABC, Mapping[str, ParameterValue]):
    expect_failure: bool = False
    invalid_parameter: str | None = None
    @property
    @abstractmethod
    def parameters(self) -> T:
        pass
    @parameters.setter
    @abstractmethod
    def parameters(self, value: T):
        pass
    def __getitem__(self, key: str) -> ParameterValue:
        return self.parameters[key]
    def __setitem__(self, key: str, value: ParameterValue) -> None:
        self.parameters[key] = value
    def __contains__(self, key: object) -> bool:
        return key in self.parameters
    def __len__(self) -> int:
        return len(self.parameters)
    def __iter__(self) -> Iterator:
        return iter(self.parameters)

@dataclass
class AcquisitionTestCaseParameters(TestCaseParameters):
    num_args: int = 1
    arg_taskfile1: str = ""
    arg_taskfile2: str = ""
    
    # Task file headers
    taskfile1_number_of_tasks: int = 1
    taskfile1_number_of_tasks_error: str = IntFieldError.CORRECT
    taskfile1_relay_type: str = ""
    taskfile2_number_of_tasks: int = 1
    taskfile2_number_of_tasks_error: str = IntFieldError.CORRECT
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
    emulator_misbehavior: str = ""
    emulator_project1_init_state: TerrameterProjectState = TerrameterProjectState.UNINITIALISED
    emulator_project2_init_state: TerrameterProjectState = TerrameterProjectState.UNINITIALISED
    
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
    
@dataclass
class AcquisitionTestCase(TestCase[AcquisitionTestCaseParameters]):
    _parameters: AcquisitionTestCaseParameters = field(default_factory=AcquisitionTestCaseParameters)
    @property
    def parameters(self) -> AcquisitionTestCaseParameters:
        return self._parameters
    @parameters.setter
    def parameters(self, value: AcquisitionTestCaseParameters) -> None:
        self._parameters = value
    