
import functools
import itertools
import random
from typing import TypeAlias

from gemeaspy.tests import _logging
from gemeaspy.tests.generator import _cache
from gemeaspy.tests.generator.parameter_spec import ParameterSpec
from gemeaspy.tests.generator.test_case import TestCase


RNGSeed: TypeAlias = None | int | float | str | bytes | bytearray
def generate_random_data(param_spec: ParameterSpec, case_count: int, seed: RNGSeed = None, invalid_rate: float = -1.0) -> list[TestCase]:
    
    # Check cache
    cache = _cache.try_load_cache(param_spec, None, f"n{case_count}_s{seed}")
    if cache is not None:
        return cache
    
    random.seed(seed)
    
    def is_duplicate(case_a: int, case_b: int):
        for param_name in param_spec:
            if test_data[case_a].parameters[param_name] != test_data[case_b].parameters[param_name]:
                return False
        return True
    
    _logging.debug("Random test case generator starting.")

    def product(iterable) -> int: 
        return functools.reduce(lambda product, x: product * x, iterable, 1)
    
    param_sizes_valid = [len(param_spec[param][0]) for param in param_spec]
    max_case_count_valid = product(param_sizes_valid)
    param_sizes_invalid = [len(param_spec[param][1]) for param in param_spec]
    
    combinations_invalid = [
            int((max_case_count_valid / param_sizes_valid[i]) * param_sizes_invalid[i]) 
            for i in range(len(param_spec))
        ]
    max_case_count_invalid: int = sum(combinations_invalid)
    max_total_case_count = max_case_count_valid + max_case_count_invalid
    
    # How many cass to generate?
    case_count = min(max_total_case_count, case_count)
    
    # How many of the cases are invalid? Reflect the distribution in the spec if not provided
    if invalid_rate < 0:
        invalid_rate = max_case_count_invalid / max_total_case_count

    # Count to make sure we don't try to generate more than the maximum
    generated_invalid = 0
    generated_valid = 0

    # Lookup table of invalid values for a given parameter name
    invalid_values = dict((param, param_spec[param][1]) for param in param_spec if len(param_spec[param][1]) > 0)

    test_data: list[TestCase] = [param_spec.TestCaseType() for _ in range(case_count)]
    for case_index in range(case_count):
        initialized = False
        is_valids_complete = generated_valid >= max_case_count_valid
        is_invalids_complete = generated_invalid < max_case_count_invalid
        use_invalid_if_possible = random.random() < invalid_rate
        is_case_invalid = is_valids_complete or (not is_invalids_complete and use_invalid_if_possible)
        invalid_param: str | None = None
        
        while not initialized or any(
            is_duplicate(case_index, x) for x in range(case_index)
        ):
            if is_case_invalid:
                invalid_param = random.choice([*invalid_values.keys()])
                invalid_value_i = random.randint(0, len(invalid_values[invalid_param])-1)
                invalid_value = invalid_values[invalid_param][invalid_value_i]
                test_data[case_index].parameters[invalid_param] = invalid_value
            # Fill out all valid params
            for param_name in param_spec:
                if param_name != invalid_param:
                    test_data[case_index].parameters[param_name] = random.choice(param_spec[param_name][0])
            initialized = True
            
        test_data[case_index].invalid_parameter = invalid_param
        if is_case_invalid:
            generated_invalid += 1
            test_data[case_index].expect_failure = True
        else:
            generated_valid += 1
            test_data[case_index].expect_failure = False

    # Verify uniqueness
    for case_a, case_b in itertools.combinations(range(case_count), 2):
        assert not is_duplicate(case_a, case_b)

    _logging.debug(f"Random test case generation finished. {len(test_data)} cases generated.")
    _cache.save_cache(test_data, param_spec, None, f"n{case_count}_s{seed}")
    return test_data
