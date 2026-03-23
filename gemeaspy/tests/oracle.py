"""This module is responsible for reviewing test execution data and determining whether or not a failure has occured"""

from dataclasses import dataclass

from gemeaspy.tests.parameter_spec import AcquisitionParameterSpec
from gemeaspy.tests.test_case import AcquisitionTestCase

@dataclass
class OracleResult:
    ok: bool
    msg: str = ""

def _evaluate_valid(test_data, stdout: str, stderr:str) -> OracleResult:
    # Find any and all faulty states
    # ...
    # Looks clean
    return OracleResult(True)

def evaluate_test(test_data: AcquisitionTestCase, task_files: list[str], stdout: str, stderr: str) -> OracleResult:
    param_spec = AcquisitionParameterSpec()
    invalid_parameter: str | None = None
    if test_data.expect_failure:
        for param_name in param_spec:
            if test_data.parameters[param_name] in param_spec[param_name][1]:
                invalid_parameter = param_name
                break
    
    match invalid_parameter:
        case None:
            return _evaluate_valid(test_data, stdout, stderr)
        case X:
            raise NotImplementedError(f"Invalid value {invalid_parameter}={repr(test_data.parameters[invalid_parameter])} not implemented in Oracle.")
    