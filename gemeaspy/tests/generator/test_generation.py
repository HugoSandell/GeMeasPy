"""Test suite generators."""

import os
import sys
from dataclasses import dataclass, field
import typing

from gemeaspy.tests.generator._generator_acts import generate_covering_array
from gemeaspy.tests.generator._generator_random import generate_random_data
from gemeaspy.tests.generator.parameter_spec import (
    ParameterSpec,
    ParamSpecEntry,
    param_values,
)
from gemeaspy.tests.generator.constraint import Constraint
from gemeaspy.tests.generator.test_case import TestCase, TestCaseParameters

# For manual testing
def _main():
    argc = len(sys.argv)
    if argc < 2 or argc > 3:
        print(f"Usage: {sys.argv[0]} <comb_strength> [rng_seed]")
        sys.exit(1)
    if not sys.argv[1].isnumeric():
        sys.stderr.write("Error: Combinatorial strength must be a positive integer!\n")
        sys.exit(1)

    @dataclass
    class TestTestCaseParameters(TestCaseParameters):
        param_a: str = ""
        param_b: int = 0
        param_c: bool = False

    @dataclass
    class TestTestCase(TestCase[TestTestCaseParameters]):
        _parameters: TestTestCaseParameters = field(default_factory=TestTestCaseParameters)
        @property
        def parameters(self) -> TestTestCaseParameters:
            return self._parameters
        @parameters.setter
        def parameters(self, value: TestTestCaseParameters) -> None:
            self._parameters = value

    @dataclass
    class TestParameterSpec(ParameterSpec):
        TestCaseType: type = TestTestCase
        param_a: ParamSpecEntry[str] = param_values(["a", "b", "c"], ["X", "Y"])
        param_b: ParamSpecEntry[int] = param_values([2, 3, 4], [-1])
        param_c: ParamSpecEntry[bool] = param_values([True, False])
    param_spec: ParameterSpec = TestParameterSpec()
    
    constraints: list[Constraint] = [
        Constraint("param_b < 3 => param_c = true")
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
    
    def print_test_cases(tests: list[TestCase], name: str):
        print_centered(padding="=+")
        input("Press Enter to continue...")
        print("\r\033[F", end="")
        print_centered(f"{name}\n")
        for i, test in enumerate(tests):
            print(f"{i + 1})\t", end="")
            for param_name in test.parameters:
                print(f"{param_name} = {test.parameters[param_name]}\t", end="")
            print()

    print_test_cases(
        acts_tests, f"{interaction_strength}-way Combinatorial tests"
    )
    print_test_cases(random_tests, "Random tests")
    print_centered(padding="=")

if __name__ == "__main__":
    _main()