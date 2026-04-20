
import csv
import json
import os
import subprocess
import tempfile
from xml.etree.ElementTree import Element, ElementTree, SubElement

import gemeaspy
from gemeaspy.tests import _logging
from gemeaspy.tests.generator import _cache
from gemeaspy.tests.generator.constraint import Constraint
from gemeaspy.tests.generator.parameter_spec import ParameterSpec, acts_type
from gemeaspy.tests.generator.parameters import ParameterValue
from gemeaspy.tests.generator.test_case import TestCase, TestCaseParameters
from gemeaspy.tests.generator.util import acts_enum_to_string, string_to_acts_enum

_ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(gemeaspy.__file__), ".."))

_ACTS_JAR = os.path.join(_ROOT_PATH, "bin", "ACTS", "acts_3.3.jar")
_ACTS_ALGORITHM = "ipog" # TODO: Use fixed algorithm or try multiple?
_ACTS_CONSTRAINT_HANDLER = "forbiddentuples" # 'solver' or 'forbiddentuples' -- same result, but solver may be faster for complex constraints.
_ACTS_TIMEOUT = 60 * 60 * 2 # 2 hour timeout should be enough unless there's a problem
_ACTS_HEAP = "4G" # How much heap space to allocate to java (Suffix G for gigabytes, M for Megabytes)

def generate_acts_file(parameter_spec: ParameterSpec, constraints: list[Constraint] = []) -> str:
    """Generate a temporary ACTS configuration file and return its path"""
    elem_system = Element("System", attrib={"name": "GeMeasPy"})
    elem_parameters = SubElement(elem_system, "Parameters")
    
    for id, param_name in enumerate(parameter_spec):
        param_type = acts_type(parameter_spec[param_name])
        elem_parameter_attrib = {"id": str(id), "name": param_name, "type": param_type.value}
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
        elem_constraint = SubElement(elem_constraints, "Constraint", attrib={"text": constraint.acts_safe_text()})
        elem_constraint_parameters = SubElement(elem_constraint, "Parameters")
        for parameter in constraint.parameters:
            SubElement(elem_constraint_parameters, "Parameter", attrib={"name": parameter})

    fd, path = tempfile.mkstemp(suffix=".xml", prefix="gemeaspytest", text=True)
    ElementTree(elem_system).write(path, xml_declaration=True)
    os.close(fd)
    return path

def generate_covering_array(param_spec: ParameterSpec, constraints: list[Constraint] = [], strength: int = 2, validate: bool = True) -> list[TestCase]:
    """Generate a Covering Array of given strength based on the provided ACTS config file"""

    # Check cache
    cache = _cache.try_load_cache(param_spec, constraints, f"t{strength}")
    if cache is not None:
        return cache

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

    _logging.debug(f"Executing ACTS. Command: {' '.join(acts_arguments)}")
    try:
        acts_out = subprocess.check_output([*acts_arguments], timeout=_ACTS_TIMEOUT).decode()
    except subprocess.CalledProcessError as e:
        e.add_note(f"ACTS exited with code {e.returncode}")
        e.add_note(f"Arguments: {e.args}")
        e.add_note(f"Output: \n{e.output}")
        _logging.error(f"ACTS exited with code {e.returncode} and output:\n{e.output}")
        raise
    except subprocess.TimeoutExpired as e:
        raise TimeoutError()
    except Exception as e:
        e.add_note("ACTS could not be executed!")
        _logging.error(f"subprocess could not execute ACTS: {str(e)}")
        raise
    finally:
        os.remove(acts_config_path)
    
    error_hints = ["generation is cancelled", "Exception", "error", "Please modify the file and retry."]
    if any(acts_out.find(search_string) >= 0 for search_string in error_hints):
        e = Exception("ACTS failed but exited normally")
        e.add_note(f"Command: {" ".join(acts_arguments)}")
        e.add_note(f"Output: \n{acts_out}")
        _logging.error(f"ACTS appears to have failed: {acts_out}")
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
                _logging.error(f"Parameter from ACTS failed to validate: {name} = {value}")
                raise validation_result
        return value
    
    test_data: list[TestCase] = []
    for raw_case in list(csv.DictReader(csv_rows)):
        case = param_spec.TestCaseType()
        for parameter_name in raw_case:
            value_json = acts_enum_to_string(raw_case[parameter_name])
            case.parameters[parameter_name] = json_to_parameter_value(parameter_name, value_json)
            is_invalid = case.parameters[parameter_name] in param_spec[parameter_name][1]
            if is_invalid:
                if case.expect_failure or case.invalid_parameter is not None:
                    raise Exception(
                        "ACTS generated test case with multiple invalid parameters"
                    )
                case.expect_failure = True
                case.invalid_parameter = parameter_name
        test_data.append(case)
    
    # Verify against constraints
    for case in test_data:
        for constraint in constraints:
            if not constraint.test(case.parameters):
                rows = []
                for parameter in constraint.parameters:
                    rows.append(f'{parameter} = {case[parameter]!r}')
                _logging.error(f"ACTS output violated constraint.\nParameters:\n{'\n'.join(rows)}\nConstraint: {constraint!r}")
                raise RuntimeError(f"ACTS output violated constraint. See {_logging.file_path}")
    
    _logging.debug(f"ACTS finished. {len(test_data)} cases generated.")
    _cache.save_cache(test_data, param_spec, constraints, f"t{strength}")
    return test_data
