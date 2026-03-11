import pytest
import os
from functools import reduce

from tests.parameter_spec import ACQUISITION_PARAM_SPEC
from tests import test_generation

def pytest_addoption(parser: pytest.Parser):
    parser.addoption("--generator", "-G", dest="generator", type=str, default="random", help="Specify which test case generator to use ('random' or 'acts')")
    parser.addoption("--size", "-I", dest="size", default=-1, type=int, help="Specify the size of the test suite (interaction strength or number of test cases). Negative values ")

def pytest_generate_tests(metafunc: pytest.Metafunc):
    if "test_case" not in metafunc.fixturenames:
        return
    i = metafunc.config.getoption("size")
    generator_name = str(metafunc.config.getoption("generator")).lower().strip()
    
    if generator_name == "random":
        max_i: int = reduce(lambda x, p: x * len(ACQUISITION_PARAM_SPEC[p]), ACQUISITION_PARAM_SPEC, 1)
        if i > max_i:
            i = max_i
        test_data = test_generation.generate_random_data(param_spec=ACQUISITION_PARAM_SPEC, max_case_count=i, seed = None)
        metafunc.parametrize("test_case", test_data)
    elif generator_name == "acts":  
        test_data = test_generation.generate_covering_array(param_spec=ACQUISITION_PARAM_SPEC, constraints=[], strength=i)
        metafunc.parametrize("test_case", test_data)
    else:
        raise ValueError(f"{generator_name} is not the name of a supported generator")