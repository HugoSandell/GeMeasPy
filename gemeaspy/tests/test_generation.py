import csv
import functools
import itertools
import json
import os
import random
import subprocess
import sys
import tempfile

from dataclasses import dataclass
from typing import TypeAlias
from xml.etree.ElementTree import Element, ElementTree, SubElement

import gemeaspy
from gemeaspy.tests import logging
from gemeaspy.tests.parameter_spec import (Constraint, ParamSpecEntry, ParameterSpec,
                                            ParameterValue, param_values)
from gemeaspy.tests.test_case import TestCase

_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(gemeaspy.__file__), ".."))

_ACTS_PARAMETER_TYPE_NUM = "0"
_ACTS_PARAMETER_TYPE_ENUM = "1"
_ACTS_PARAMETER_TYPE_BOOLEAN = "2"

_ACTS_JAR = f"{_ROOT_PATH}/bin/ACTS/acts_3.3.jar"
_ACTS_ALGORITHM = "ipog" # TODO: Use fixed algorithm or try multiple?
_ACTS_CONSTRAINT_HANDLER = "forbiddentuples" # 'solver' or 'forbiddentuples' -- same result, but solver may be faster for complex constraints.
_ACTS_TIMEOUT = 60 * 60 * 2 # 2 hour timeout should be enough unless there's a problem
_ACTS_HEAP = "4G" # How much heap space to allocate to java (Suffix G for gigabytes, M for Megabytes)

# It is unfortunately necessary to replace some characters for ACTS
ACTS_ENUM_UNSAFE_CHARS = ["\"", ",", "&", "%", "+", "<", ">", "="]
def string_to_acts_enum(s: str) -> str:
    """Replace unsafe characters for processing in ACTS"""
    for char in ACTS_ENUM_UNSAFE_CHARS:
        s = s.replace(char, f"@{char.encode("ascii").hex()}@")
    return s
def acts_enum_to_string(s: str) -> str:
    """Recover unsafe characters from ACTS"""
    for char in ACTS_ENUM_UNSAFE_CHARS:
        s = s.replace(f"@{char.encode("ascii").hex()}@", char)
    return s

def acts_type(parameter_values: ParamSpecEntry | list[ParameterValue]) -> str:
    """Determine the appropriate ACTS type for the given parameter"""
    if type(parameter_values) == tuple:
        parameter_values = [value for component in parameter_values for value in component]
    if all(isinstance(v, bool) for v in parameter_values):
        return _ACTS_PARAMETER_TYPE_BOOLEAN
    if all(isinstance(v, int) for v in parameter_values):
        return _ACTS_PARAMETER_TYPE_NUM
    return _ACTS_PARAMETER_TYPE_ENUM

def generate_acts_file(parameter_spec: ParameterSpec, constraints: list[Constraint] = []) -> str:
    """Generate a temporary ACTS configuration file and return its path"""
    elem_system = Element("System", attrib={"name": "GeMeasPy"})
    elem_parameters = SubElement(elem_system, "Parameters")
    
    for id, param_name in enumerate(parameter_spec):
        param_type = acts_type(parameter_spec[param_name])
        elem_parameter_attrib = {"id": str(id), "name": param_name, "type": param_type}
        elem_parameter = SubElement(elem_parameters, "Parameter", attrib=elem_parameter_attrib)
        elem_values = SubElement(elem_parameter, "values")
        for valid_value in parameter_spec[param_name][0]:
            SubElement(elem_values, "value").text = string_to_acts_enum(json.dumps(valid_value))
        SubElement(elem_parameter, "basechoices")
        elem_invalid_values = SubElement(elem_parameter, "invalidValues")
        for invalid_value in parameter_spec[param_name][1]:
            SubElement(elem_invalid_values, "invalidValue").text = f"{string_to_acts_enum(json.dumps(invalid_value))}"
    SubElement(elem_system, "OutputParameters")
    SubElement(elem_system, "Relations")
    
    elem_constraints = SubElement(elem_system, "Constraints")
    for constraint in constraints:
        elem_constraint = SubElement(elem_constraints, "Constraint", attrib={"text": constraint.text})
        elem_constraint_parameters = SubElement(elem_constraint, "Parameters")
        for parameter in constraint.parameters:
            SubElement(elem_constraint_parameters, "Parameter", attrib={"name": parameter})
    
    fd, path = tempfile.mkstemp(suffix=".xml", prefix="gemeaspytest", text=True)
    ElementTree(elem_system).write(path, xml_declaration=True)
    os.close(fd)
    return path


def generate_covering_array(param_spec: ParameterSpec, constraints: list[Constraint] = [], strength: int = 2, validate: bool = True) -> list[TestCase]:
    """Generate a Covering Array of given strength based on the provided ACTS config file"""

    if not os.path.exists(_ACTS_JAR):
        raise FileNotFoundError(f"ACTS was not found at {_ACTS_JAR}")
    
    out_file_dir = tempfile.mkdtemp("gemeaspytest")
    out_file_path = os.path.join(out_file_dir, "acts_output.csv")
    
    def path_escape(path: str) -> str:
        return path.replace("\\", "/")
    
    acts_config_path = generate_acts_file(param_spec, constraints)
    
    acts_arguments = [
        "java", f"-Xms{_ACTS_HEAP}", f"-Xmx{_ACTS_HEAP}", "-Ddoi=" + str(strength), "-Dalgo=" + _ACTS_ALGORITHM, 
        "-Doutput=csv", "-Dchandler=" + _ACTS_CONSTRAINT_HANDLER, "-jar", _ACTS_JAR, 
        path_escape(acts_config_path), 
        path_escape(out_file_path)
    ]

    logging.debug(f"Executing ACTS. Command: {' '.join(acts_arguments)}")
    try:
        acts_out = subprocess.check_output([*acts_arguments], timeout=_ACTS_TIMEOUT).decode()
    except subprocess.CalledProcessError as e:
        e.add_note(f"ACTS exited with code {e.returncode}")
        e.add_note(f"Arguments: {e.args}")
        e.add_note(f"Output: \n{e.output}")
        logging.error(f"ACTS exited with code {e.returncode} and output:\n{e.output}")
        raise
    except subprocess.TimeoutExpired as e:
        raise TimeoutError()
    except Exception as e:
        e.add_note("ACTS could not be executed!")
        logging.error(f"subprocess could not execute ACTS: {str(e)}")
        raise
    finally:
        os.remove(acts_config_path)
    
    error_hints = ["generation is cancelled", "Exception", "error", "Please modify the file and retry."]
    if any(acts_out.find(search_string) >= 0 for search_string in error_hints):
        e = Exception("ACTS failed but exited normally")
        e.add_note(f"Command: {" ".join(acts_arguments)}")
        e.add_note(f"Output: \n{acts_out}")
        logging.error(f"ACTS appears to have failed: {acts_out}")
        raise e
    
    csv_rows = []
    with open(out_file_path, mode="r") as out_file:
        row = out_file.readline()
        # Skip comments
        while str.strip(row).startswith("#"):
            row = out_file.readline()
        csv_rows.append(row)
        csv_rows.extend(out_file)

    # Cleanup
    if os.path.exists(out_file_path):
        os.remove(out_file_path)
    if os.path.exists(out_file_dir):
        os.rmdir(out_file_dir)
    
    def json_to_parameter_value(name, value_json) -> ParameterValue:
        value = json.loads(value_json)
        if validate:
            validation_result = param_spec.validate_parameter(name, value)
            if validation_result != None:
                logging.error(f"Parameter from ACTS failed to validate: {name} = {value}")
                raise validation_result
        return value
    
    test_data: list[TestCase] = []
    for raw_case in list(csv.DictReader(csv_rows)):
        case = param_spec.TestCaseType()
        for parameter_name in raw_case:
            value_json = acts_enum_to_string(raw_case[parameter_name])
            case[parameter_name] = json_to_parameter_value(parameter_name, value_json)
        test_data.append(case)
    logging.debug(f"ACTS finished. {len(test_data)} cases generated.")
    return test_data


RNGSeed: TypeAlias = None | int | float | str | bytes | bytearray
def generate_random_data(param_spec: ParameterSpec, case_count: int, seed: RNGSeed = 0) -> list[TestCase]:
    random.seed(seed)
    
    def is_duplicate(case_a: int, case_b: int):
        for param_name in param_spec:
            if test_data[case_a][param_name] != test_data[case_b][param_name]:
                return False
        return True
    
    logging.debug("Random test case generator starting.")

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
    
    # How many of the cases are invalid? Reflect the distribution in the spec
    invalid_rate: float = max_case_count_invalid / max_total_case_count

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
        
        while not initialized or any(
            is_duplicate(case_index, x) for x in range(case_index)
        ):
            # "" Signifies no invalid
            invalid_param = "" 
            if is_case_invalid:
                invalid_param = random.choice([*invalid_values.keys()])
                invalid_value_i = random.randint(0, len(invalid_values[invalid_param])-1)
                invalid_value = invalid_values[invalid_param][invalid_value_i]
                test_data[case_index][invalid_param] = invalid_value
            # Fill out all valid params
            for param_name in param_spec:
                if param_name != invalid_param:
                    test_data[case_index][param_name] = random.choice(param_spec[param_name][0])
            initialized = True
        if is_case_invalid:
            generated_invalid += 1
        else:
            generated_valid += 1

    # Verify uniqueness
    for case_a, case_b in itertools.combinations(range(case_count), 2):
        assert not is_duplicate(case_a, case_b)

    logging.debug(f"Random test case generation finished. {len(test_data)} cases generated.")
    return test_data

# For manual testing
def _main():
    argc = len(sys.argv)
    if argc < 2 or argc > 3:
        print(f"Usage: {sys.argv[0]} <comb_strength> [rng_seed]")
        exit(1)
    if not sys.argv[1].isnumeric():
        sys.stderr.write("Error: Combinatorial strength must be a positive integer!\n")
        exit(1)
    
    @dataclass
    class TestTestCase(TestCase):
        param_a: str = ""
        param_b: int = 0
        param_c: bool = False

    @dataclass
    class TestParameterSpec(ParameterSpec):
        TestCaseType: type = TestTestCase
        param_a: ParamSpecEntry[str] = param_values(["a", "b", "c"], ["X", "Y"])
        param_b: ParamSpecEntry[int] = param_values([2, 3, 4], [-1])
        param_c: ParamSpecEntry[bool] = param_values([True, False])
    param_spec: ParameterSpec = TestParameterSpec()
    
    constraints: list[Constraint] = [
        Constraint("param_b < 3 => param_c = true", parameters=["param_b", "param_c"])
    ]
    
    rng_seed = None
    if argc == 4:
        rng_seed = sys.argv[2]
    interaction_strength = int(sys.argv[1])
    
    if interaction_strength > len(param_spec):
        interaction_strength = len(param_spec)
    
    acts_tests: list[TestCase] = generate_covering_array(param_spec, constraints, interaction_strength, validate=False)
    random_tests: list[TestCase] = generate_random_data(param_spec, len(acts_tests), rng_seed)
    
    # Print results 
    def print_centered(msg: str="", padding: str=" "):
        total_length = os.get_terminal_size().columns
        padding_per_side = total_length / 2 / len(padding) - len(msg) / 2
        main_padding = padding * int(padding_per_side)
        print(f"{main_padding}{msg}{main_padding}", end="")
        print(padding[:total_length - len(main_padding) * 2 - len(msg)])
    
    print()
    print_centered(padding="=")
    print_centered("Parameters")
    print_centered("name : valid values, invalid values")
    for param_name in param_spec:
        print(f"{param_name}:\t", end="")
        print(", ".join([str(value) for value in param_spec[param_name]]))
    print_centered(padding="-")
    print_centered("Constraints")
    for i, constraint in enumerate(constraints):
        print(f"{i+1}) {constraint.text}")
    
    def print_test_cases(tests, name):
        print_centered(padding="=+")
        input("Press Enter to continue...")
        print("\r\033[F", end="")
        print_centered(f"{name}\n")
        for i, test in enumerate(tests):
            print(f"{i + 1})\t", end="")
            for param_name in test:
                print(f"{param_name} = {test[param_name]}\t", end="")
            print()

    print_test_cases(
        acts_tests, f"{interaction_strength}-way Combinatorial tests"
    )
    print_test_cases(random_tests, "Random tests")
    print_centered(padding="=")

if __name__ == "__main__":
    _main()