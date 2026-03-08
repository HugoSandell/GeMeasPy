from typing import TypeAlias

TestCase: TypeAlias = dict[str, str | int | bool]
"""A list of test cases. Each test case is a dictionary of parameter name:value pairs"""
