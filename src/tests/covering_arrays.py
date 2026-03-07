import typing
from typing import TypeAlias, Callable
import subprocess
import tempfile
import os
import csv

CoveringArray: TypeAlias = list[dict[str, str]]
"""A list of test cases. Each test case is a dictionary of parameter name:value pairs"""

ACTS_JAR = "../bin/ACTS/acts_basic_1.0 3.jar"
ALGORITHM = "ipog"

def generate_array(acts_config_path: str, strength: int = 2) -> CoveringArray:
    """Generate a Covering Array of given strength based on the provided ACTS config file"""
    out_file_dir = tempfile.mkdtemp("gemeaspytest")
    out_file_path = os.path.join(out_file_dir, "acts_output.csv")
    
    def path_escape(path: str) -> str:
        return path.replace("\\", "/")
    
    acts_arguments = ["java", "-Ddoi=" + str(strength), "-Dalgo=" + ALGORITHM, "-Doutput=csv",
                      "-jar", ACTS_JAR, path_escape(acts_config_path), path_escape(out_file_path)]
    m: subprocess.CompletedProcess = subprocess.run([*acts_arguments])
    m.check_returncode()

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

    return list(csv.DictReader(csv_rows))

if __name__ == "__main__":
    # For manual testing
    print(generate_array("tests/data/acts_config.xml", 3))