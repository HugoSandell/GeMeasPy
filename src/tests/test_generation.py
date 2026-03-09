import typing
from typing import TypeAlias
import subprocess
import tempfile 
import os
import itertools
import sys
import csv
import json
from xml.etree.ElementTree import ElementTree, Element, SubElement
import random

from tests import parameter_spec
from tests.parameter_spec import ParameterSpec, ParameterValue

sys.path.insert(
    1, _SRC_PATH := os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)
from tests.test_case import TestCase

_ACTS_JAR = f"{_SRC_PATH}/../bin/ACTS/acts_basic_1.0.jar"
_ACTS_ALGORITHM = "ipog"

def generate_acts_file(parameter_spec: ParameterSpec) -> str:
    """Generate a temporary ACTS configuration file and return its path"""
    elem_system = Element("System", attrib={"name": "GeMeasPy"})
    elem_parameters = SubElement(elem_system, "Parameters")
    
    for id, param_name in enumerate(parameter_spec):
        elem_parameter = SubElement(elem_parameters, "Parameter", attrib={"id": str(id), "name": param_name, "type": "1"})
        elem_values = SubElement(elem_parameter, "values")
        for value in parameter_spec[param_name]:
            SubElement(elem_values, "value").text = json.dumps(value)
        SubElement(elem_parameter, "basechoices")
        SubElement(elem_parameter, "invalidValues")
    SubElement(elem_system, "OutputParameters")
    SubElement(elem_system, "Relations")
    SubElement(elem_system, "Constraints")
    
    fd, path = tempfile.mkstemp(suffix=".xml", prefix="gemeaspytest", text=True)
    ElementTree(elem_system).write(path, xml_declaration=True)
    os.close(fd)
    return path

def generate_covering_array(acts_config_path: str, strength: int = 2) -> list[TestCase]:
    """Generate a Covering Array of given strength based on the provided ACTS config file"""
    
    if not os.path.exists(_ACTS_JAR):
        raise FileNotFoundError(f"ACTS was not found at {_ACTS_JAR}")
    
    out_file_dir = tempfile.mkdtemp("gemeaspytest")
    out_file_path = os.path.join(out_file_dir, "acts_output.csv")
    
    def path_escape(path: str) -> str:
        return path.replace("\\", "/")
    
    acts_arguments = ["java", "-Ddoi=" + str(strength), "-Dalgo=" + _ACTS_ALGORITHM, "-Doutput=csv",
                      "-jar", _ACTS_JAR, path_escape(acts_config_path), path_escape(out_file_path)]

    try:
        acts_out = subprocess.check_output([*acts_arguments]).decode()
    except subprocess.CalledProcessError as e:
        e.add_note(f"ACTS exited with code {e.returncode}")
        e.add_note(f"Arguments: {e.args}")
        e.add_note(f"Output: \n{e.output}")
        raise
    except Exception as e:
        e.add_note("ACTS could not be executed!")
        raise
    
    if acts_out.find("Exception") >= 0 or acts_out.find("error") >= 0:
        e = Exception("ACTS failed but exited normally")
        e.add_note(f"Command: {" ".join(acts_arguments)}")
        e.add_note(f"Output: \n{acts_out}")
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
        validation_result = parameter_spec.validate_parameter(name, value)
        if validation_result != None:
            raise validation_result
        return value
    
    test_data: list[TestCase] = []
    for raw_case in list(csv.DictReader(csv_rows)):
        case = {}
        for parameter_name in raw_case:
            case[parameter_name] = json_to_parameter_value(parameter_name, raw_case[parameter_name])
        test_data.append(case)
    return test_data

RNGSeed: TypeAlias = None | int | float | str | bytes | bytearray
def generate_random_data(parameter_spec: ParameterSpec, max_case_count: int, seed: RNGSeed = 0) -> list[TestCase]:
    random.seed(seed)
    
    def is_duplicate(case_a: int, case_b: int):
        for param_name in parameter_spec:
            if test_data[case_a][param_name] != test_data[case_b][param_name]:
                return False
        return True
    
    # TODO: make sure this won't loop endlessly if there are more cases than combinations 
    case_count = max_case_count
    
    test_data: list[TestCase] = [dict() for _ in range(case_count)]
    for case_index in range(case_count):
        while len(test_data[case_index]) == 0 or any([is_duplicate(case_index, x) for x in range(case_index)]):
            for param_name in parameter_spec:
                test_data[case_index][param_name] = random.choice(parameter_spec[param_name])

    # Verify uniqueness
    for case_a, case_b in itertools.combinations(range(case_count), 2):
        assert not is_duplicate(case_a, case_b)
        
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
    
    param_spec: ParameterSpec = {"param_a": ["a", "b", "c"], "param_b": [1, 2, 3], "param_c": [True, False]}
    
    rng_seed = None
    if argc == 4:
        rng_seed = sys.argv[2]
    acts_file = generate_acts_file(param_spec)
    interaction_strength = int(sys.argv[1])
    
    if interaction_strength > len(param_spec):
        interaction_strength = len(param_spec)
    
    combinatorial_tests = generate_covering_array(acts_file, interaction_strength)
    random_tests = generate_random_data(param_spec, len(combinatorial_tests), rng_seed)
    
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
    print_centered("name : values")
    for i, param_name in enumerate(param_spec):
        print(f"{param_name}:\t", end="")
        print(", ".join([str(value) for value in param_spec[param_name]]))

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
        combinatorial_tests, f"{interaction_strength}-way Combinatorial tests"
    )
    print_test_cases(random_tests, "Random tests")
    print_centered(padding="=")
    os.remove(acts_file)

if __name__ == "__main__":
    _main()