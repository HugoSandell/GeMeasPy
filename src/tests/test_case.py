from typing import TypeAlias
from tests.parameter_spec import ParameterValue

TestCase: TypeAlias = dict[str, ParameterValue]
"""A list of test cases. Each test case is a dictionary of parameter name:value pairs"""
