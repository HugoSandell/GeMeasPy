from functools import reduce
import os

import pytest

from gemeaspy.tests import test_generation
from gemeaspy.tests.parameter_spec import ACQUISITION_PARAM_SPEC
from gemeaspy.tests.util import random_string

@pytest.fixture(autouse=True)
def environment_variable_debug():
    os.environ["DEBUG"] = "1"

def pytest_addoption(parser: pytest.Parser):
    parser.addoption("--generator", "-G", dest="generator", type=str, default="acts", help="Specify which test case generator to use ('random' or 'acts')")
    parser.addoption("--size", "-N", dest="size", default=100, type=int, help="Specify the number of test cases. (random only)")
    parser.addoption("--strength", "-T", dest="strength", default=3, type=int, help="Specify the test suite interaction strength. (ACTS only)")
    parser.addoption("--seed", "-S", dest="seed", default=None, type=int, help="Specify the random seed. (random only)")

def pytest_generate_tests(metafunc: pytest.Metafunc):
    if "test_case" not in metafunc.fixturenames:
        return
    t = metafunc.config.getoption("strength")
    N = metafunc.config.getoption("size")
    random_seed = metafunc.config.getoption("seed")
    generator_name = str(metafunc.config.getoption("generator")).lower().strip()
    
    if generator_name == "acts":
        if t <= 0:
            raise ValueError("Interaction strength must be greater than 0")
        elif t > len(ACQUISITION_PARAM_SPEC):
            raise ValueError(f"Interaction strength must not be greater than {len(ACQUISITION_PARAM_SPEC)}")
        test_data = test_generation.generate_covering_array(param_spec=ACQUISITION_PARAM_SPEC, constraints=[], strength=t)
        metafunc.parametrize("test_case", test_data)
    elif generator_name == "random":
        max_N: int = reduce(lambda x, p: x * len(ACQUISITION_PARAM_SPEC[p]), ACQUISITION_PARAM_SPEC, 1)
        if N <= 0:
            raise ValueError("Test suite size must be greater than 0")
        if N > max_N:
            raise ValueError(f"Test suite size must not be greater than {max_N}")    
        test_data = test_generation.generate_random_data(param_spec=ACQUISITION_PARAM_SPEC, case_count=N, seed=random_seed)
        metafunc.parametrize("test_case", test_data)
    else:
        raise ValueError(f"'{generator_name}' is not a valid test case generator.")