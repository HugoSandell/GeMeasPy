from collections.abc import Callable
import json
import typing

from gemeaspy.tests import test_generation
from time import time

from gemeaspy.tests.parameter_spec import ACQUISITION_CONSTRAINTS, ACQUISITION_PARAM_SPEC
from gemeaspy.tests.test_case import TestCase

_SEC = 1.0
_MIN = 60.0 * _SEC
_HOUR = 60.0 * _MIN

MAX_EXECUTION_TIME: float = 00 * _HOUR + 3 * _MIN + 0 * _SEC

def timer[T](f: Callable[..., T]) -> Callable[..., tuple[T, float]]:
    def _f(*args) -> tuple[T, float]:
        start_time = time()
        retval = f(*args)
        end_time = time()
        return (retval, end_time - start_time)
    return _f

@timer
def generate_covering_array(strength: int) -> list[TestCase]:
    return test_generation.generate_covering_array(
        param_spec=ACQUISITION_PARAM_SPEC, 
        constraints=ACQUISITION_CONSTRAINTS,
        strength = strength,
        validate=True
    )

@timer
def generate_random_array(size: int) -> list[TestCase]:
    return test_generation.generate_random_data(
        param_spec=ACQUISITION_PARAM_SPEC,
        case_count=size,
        seed=0
    )

def save_acts_suite(strength: int, suite: list[TestCase]):
    filename = f"{test_generation._ROOT_PATH}/test_data/suite_acts_{strength}.json"
    with open(filename, "w") as fp:
        json.dump([case.__dict__ for case in suite], fp)

def save_random_suite(strength_equivalent: int, suite: list[TestCase]):
    filename = f"{test_generation._ROOT_PATH}/test_data/suite_random_{strength_equivalent}.json"
    with open(filename, "w") as fp:
        json.dump([case.__dict__ for case in suite], fp)

if __name__ == "__main__":
    covering_arrays_metaparameters = []
    t = 1
    test_generation._ACTS_TIMEOUT = MAX_EXECUTION_TIME
    last_execution_time: float = 0.0
    
    suite_sizes: dict[int, int] = {}
    
    while last_execution_time < MAX_EXECUTION_TIME:
        print(f"Running ACTS generator with t={t}")
        try:
            test_suite, last_execution_time = generate_covering_array(t)
            save_acts_suite(t, test_suite)
            suite_sizes[t] = len(test_suite)
        except TimeoutError:
            print(f"ACTS timed out")
            break
        if last_execution_time < MAX_EXECUTION_TIME:
            t += 1

    for t in suite_sizes:
        size = suite_sizes[t]
        print(f"Running Random generator with size={size}")
        try:
            test_suite, last_execution_time = generate_random_array(size)
            save_random_suite(size, test_suite)
        except TimeoutError:
            print(f"Random generator timed out")
            break