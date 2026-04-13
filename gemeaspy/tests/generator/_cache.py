"""Caching functions for test suites"""

import hashlib
import json
import os
import typing
from os import path

import gemeaspy
from gemeaspy.tests import _logging

from gemeaspy.tests.generator.constraint import Constraint
from gemeaspy.tests.generator.parameter_spec import ParameterSpec
from gemeaspy.tests.generator.test_case import TestCase, TestCaseParameters

_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(gemeaspy.__file__), ".."))
_CACHE_DIR_PATH = os.path.join(_ROOT_PATH, "test_data", "input_cache")

def _get_cache_file_path(
    param_spec: ParameterSpec, constraints: list[Constraint] | None, id_str: str
) -> str:
    param_spec_hash = hashlib.sha256(
        repr((param_spec, constraints)).encode()
    ).hexdigest()
    return f"{param_spec_hash}_{id_str}.json"

def try_load_cache(
    param_spec: ParameterSpec, constraints: list[Constraint] | None, id_str: str
) -> None | list[TestCase[TestCaseParameters]]:
    cache_file_path = path.join(_CACHE_DIR_PATH, _get_cache_file_path(param_spec, constraints, id_str))
    if not os.path.isfile(cache_file_path):
        return None
    with open(cache_file_path, "r") as fp:
        suite_json = json.load(fp)
        if not isinstance(suite_json, list):
            raise TypeError(f"Expected list in input cache file '{cache_file_path}'")
    suite = []
    for case_json in suite_json:
        try:
            parameters_json = case_json["parameters"]
            case = param_spec.TestCaseType()
            case.expect_failure = case_json["expect_failure"]
            case.invalid_parameter = case_json["invalid_parameter"]
            if case.expect_failure and (
                case.invalid_parameter is None 
                or str(case.invalid_parameter) not in param_spec
            ):
                _logging.warning(f"Cache file contained invalid invalid_parameter {repr(case.invalid_parameter)}")
                return None
            for param_name in case.parameters:
                case.parameters[param_name] = parameters_json[param_name]
            suite.append(case)
        except KeyError as e:
            _logging.warning(f"Cache file contained invalid key {repr(e.args[0])}")
            return None
    _logging.debug(f"Loaded cache for {id_str}")
    return suite


def save_cache[T: TestCase](
    suite: list[T],
    param_spec: ParameterSpec,
    constraints: list[Constraint] | None,
    id_str: str
):
    cache_file_path = path.join(_CACHE_DIR_PATH, _get_cache_file_path(param_spec, constraints, id_str))
    os.makedirs(_CACHE_DIR_PATH, exist_ok=True)
    with open(cache_file_path, "w") as fp:
        json.dump([
                {"parameters": case.parameters.__dict__, 
                    "expect_failure": case.expect_failure, 
                    "invalid_parameter": case.invalid_parameter
                } for case in suite
            ], fp)