# Test data generator
<sup><span style="opacity:0.6">Last updated on June 7 2026</span></sup><br>
This module produces parameter sets for the end-to-end tests of GeMeasPy. Each test run needs concrete values for every input the software reads: command-line arguments, configuration files, task files, connection settings, and the initial state of the emulated Terrameter. Each parameter in the specification has a list of valid values (inputs the software should accept) and invalid values (inputs it should reject). The generator selects one value per parameter, filtered by constraints that rule out internally inconsistent combinations. Two strategies are available: a covering array produced by ACTS and uniform random sampling.

## Usage

```python
from gemeaspy.tests.generator import (
    ACQUISITION_PARAM_SPEC,
    ACQUISITION_CONSTRAINTS,
    generate_covering_array,
    generate_random_data,
)

acts_tests = generate_covering_array(
    ACQUISITION_PARAM_SPEC, ACQUISITION_CONSTRAINTS, strength=2
)
random_tests = generate_random_data(
    ACQUISITION_PARAM_SPEC,
    ACQUISITION_CONSTRAINTS,
    case_count=len(acts_tests),
    seed=42,
)
```

Each call returns a list of `AcquisitionTestCase` objects. `test_main.py` consumes these as pytest parameters.

## Files

| File                     | Role                                                                              |
| ------------------------ | --------------------------------------------------------------------------------- |
| `__init__.py`            | Re-exports the public API.                                                        |
| `parameters.py`          | The `ParameterValue` type alias.                                                  |
| `parameter_spec.py`      | `ParameterSpec`, `AcquisitionParameterSpec`, and `ACQUISITION_CONSTRAINTS`.       |
| `test_case.py`           | `TestCase`, `TestCaseParameters`, and the acquisition subclasses.                 |
| `constraint.py`          | Parses and evaluates ACTS-style constraint strings.                               |
| `int_field_error.py`     | Enum of categorical error modes for a stringified integer field.                  |
| `test_generation.py`     | Public entry points to both generators, and a manual test main.                   |
| `_generator_acts.py`     | Calls ACTS to produce a covering array.                                           |
| `_generator_random.py`   | Generates random test cases under constraints.                                    |
| `_cache.py`              | Reads and writes JSON caches of generated suites.                                 |
| `util.py`                | String encoding helpers for ACTS.                                                 |

## Notes on the implementation

### Parameter specifications

`ParameterSpec` is a class. Each field is a `ParamSpecEntry`, a pair of lists holding the valid values and the invalid values for that parameter. The helpers `param_values()` and `enum_param_values()` build entries with the right factory. The class attribute `TestCaseType` ties a spec to the test case class it produces.

`AcquisitionParameterSpec` is a subclass of `ParameterSpec` that declares every parameter the acquisition tests need. A few examples:

- `num_args`: valid `[1, 2]`, invalid `[0]`.
- `connection_port`: valid `[VALID_PORT]`, invalid `["", 0, -1, 65536, None]`.
- `emulator_project1_init_state`: a `TerrameterProjectState` enum, all
  values valid.

Names like `VALID_TASKFILE1`, `INVALID_FILE`, and `VALID_PORT` are placeholders. Pytest fixtures substitute them with real paths and ports once a concrete test case runs.

Some integer fields in task files are transmitted as strings, so they can fail in ways a plain integer parameter cannot: the field might be empty, non-numeric, or off by one. These are modelled with paired parameters: an integer parameter for the correct value (e.g. `taskfile1_number_of_tasks`) and a companion `_error` parameter of type `IntFieldError` (e.g. `taskfile1_number_of_tasks_error`). `CORRECT` is the only valid `IntFieldError` value; `EMPTY`, `STRING`, `MINUS_1`, and `PLUS_1` are all invalid. At test runtime, `IntFieldError.resolve(value)` converts the integer to the actual string written to the file.

A `_validate_spec()` call at module load checks that every field in the spec has a matching field in the test case parameters, and vice versa. If you add a parameter to one, you must add it to the other.

### Test cases

`TestCaseParameters` behaves like a dict but only accepts keys that are declared as attributes of the subclass. This catches typos at runtime instead of accepting wrong keys silently. `AcquisitionTestCaseParameters` lists every parameter the acquisition tests use.

A `TestCase` wraps a `TestCaseParameters` instance and adds two fields: `expect_failure`, set when the case includes an invalid value, and `invalid_parameter`, the name of the offending parameter or `None`. Both generators set these consistently, so the test oracle (the code that checks whether the acquisition outcome matches the expectation) can determine the expected result from the test case alone.

### Constraints

`Constraint` parses an ACTS-style constraint string. The supported operators are:

- Relational: `=`, `==`, `!=`, `<`, `<=`, `>`, `>=`. `=` and `==` are
  treated as the same operator.
- Boolean: `&&`, `||`, `=>`. `=>` binds least tightly and is
  right-associative.
- Arithmetic: `+`, `-`, `*`, `/`, `%`. Integer operands only.

Parsing has two stages. `_tokenize()` produces a flat list of tokens, then `_ConstraintParser` builds a tree using recursive descent. The tree is kept on the `Constraint` instance and used in two ways. `Constraint.test(params)` evaluates the tree against a dict of parameter bindings. Both generators use this: the random generator to filter candidate cases, and the covering-array generator to verify each row of ACTS output. `Constraint.parameters` lists the parameter names that appear in the constraint, which ACTS expects in the XML configuration.

The `__main__` block of `constraint.py` compares the parser's evaluation against Python's own evaluation on a random sample of bindings. Run this after changes to the parser or evaluator.

The constraint format follows the ACTS convention. For examples and a description of precedence rules, see the constraints chapter of the ACTS user guide in `bin/ACTS/`.

### ACTS string encoding

ACTS treats several characters in enumerated values as syntax: `"`, `,`, `&`, `%`, `+`, `<`, `>`, `=`. `util.obj2acts()` serialises a value as JSON and replaces each unsafe character with `@<hex>@`. `acts2obj()` reverses the process when reading ACTS output. All values handed to ACTS or read back from it pass through these functions.

### Covering array generation

`generate_covering_array()` writes a temporary ACTS XML configuration from the spec and constraints, then runs `acts_3.3.jar` as a Java subprocess. The result is a t-way covering array: a test set in which every combination of values of any t parameters appears in at least one test. ACTS supports t between 1 and 6.

The generator uses three features from the ACTS Advanced Version. Negative testing combines each invalid parameter value with every (t-1)-way combination of valid values, and limits each test to at most one invalid value. The one-invalid-value bound avoids the masking effect that can occur when several invalid values appear in the same test, and both generators here enforce it. Constraint support excludes combinations that violate the supplied constraints. Base choices are values declared per parameter that ACTS uses when filling in parameters that are not yet constrained.

`generate_acts_file()` writes an XML configuration in the format described in section 2 of the ACTS user guide (`bin/ACTS/acts_user_guide_for_basic1.0_and_advanced3.3_versions_nov23.pdf`). Each parameter declaration includes a type (`0` for integer, `1` for enumerated, `2` for boolean), a list of valid values, an empty `basechoices` element, and a list of invalid values. Each constraint is declared with the original text and the list of parameter names it references.

The subprocess runs with these options. They are defined as constants at the top of `_generator_acts.py` and can be changed there. See the user guide for the full set of options.

- `-Dalgo=ipog`. The IPOG algorithm. IPOG and IPOG-F are the only ACTS
  algorithms that support both constraints and negative testing, and
  the user guide recommends IPOG for systems of fewer than about
  twenty parameters with ten or fewer values per parameter on average.
- `-Dchandler=forbiddentuples`. Constraints are handled by the
  forbidden-tuples method, which the user guide describes as the
  default. The alternative is `solver`, which may be faster for
  complex constraint sets.
- `-Doutput=csv`. The output is parsed as CSV.
- `-Ddoi=<strength>`. The interaction strength, passed through from
  the `strength` argument.
- `-Xms1G -Xmx8G`. JVM initial and maximum heap sizes. The user guide
  notes that the default heap may not be sufficient for large
  configurations.

The subprocess timeout is set by the `_ACTS_TIMEOUT` constant.

After ACTS returns, the generator parses each CSV row into an `AcquisitionTestCase`, decoding values with `acts2obj` and flagging cases that contain a known-invalid value. It also verifies that every case satisfies every constraint. ACTS sometimes signals failure by printing an error and exiting cleanly, so the generator scans the output for known error strings too.

### Random generation

`generate_random_data()` produces a list of cases of the requested size:

1. It enumerates the number of constraint-satisfying combinations of valid values, and the number of constraint-satisfying combinations with exactly one invalid value. These give the upper bound on case count and the default invalid rate.
2. For each case, it decides whether the case should be valid or invalid, weighted by `invalid_rate`. When not supplied, the rate matches the natural ratio from step 1.
3. It draws values at random (one invalid if required, the rest valid) and resamples until the case is unique and satisfies every constraint.

The seed argument accepts `None`, an int, or a string. `None` picks a random 64-bit seed and records it in the cache key, so the result is stable across calls.

The generator enforces the one-invalid-value rule from ACTS negative testing here too, so the oracle can apply the same logic to both suites.

### Caching

`_cache.py` writes each generated suite to `test_data/input_cache/<hash>_<tag>.json`. The hash comes from the specification and constraints. The tag distinguishes generators: `t2` for a strength-2 covering array, `n100_s<seed>` for 100 random cases with the given seed. Both generators check the cache before running and write the result afterwards. To force regeneration, delete the relevant JSON file.

The cache key is sensitive to anything that changes the [`repr`](https://docs.python.org/3/library/functions.html#repr) of the spec or constraints, so adding a value to a parameter or rewording a constraint invalidates the cache automatically.

## The acquisition specification and its constraints

`ACQUISITION_CONSTRAINTS` enforces consistency between parameters that are not independent. Helper functions in `parameter_spec.py` generate most entries:

- `_constraints_for_unused_taskfile(n)`: when fewer than `n` task files
  are passed, or task file `n` is invalid, force its header parameters
  to their first valid value.
- `_constraints_for_unused_task(...)`: when a task file declares fewer
  tasks than `n`, force task `n`'s parameters to their first valid
  value.
- `_constraints_for_invalid_task_parameters(...)`: when a task has any
  invalid parameter, the project init state must be one that does not
  require the task to exist.

The rest are written by hand and rule out states such as "project 2 has tasks but task file 2 was not provided", or "both projects are in a non-`UNINITIALISED` state at the same time".

To add a constraint, write it as a string, wrap it in `Constraint(...)`, and append it to `ACQUISITION_CONSTRAINTS`. Both generators will pick it up.

## Where to look to fix or extend things

| To...                                                  | Edit                                                            |
| ------------------------------------------------------ | --------------------------------------------------------------- |
| Add an acquisition parameter                           | `AcquisitionTestCaseParameters` in `test_case.py` and `AcquisitionParameterSpec` in `parameter_spec.py`. |
| Add a categorical error mode for an int field          | `IntFieldError` in `int_field_error.py`.                        |
| Tighten or relax a constraint                          | `ACQUISITION_CONSTRAINTS` in `parameter_spec.py`.               |
| Change the ACTS interaction strength                   | the `strength` argument to `generate_covering_array()`.         |
| Change the ACTS algorithm, heap, or constraint handler | constants at the top of `_generator_acts.py`. See the ACTS user guide for the full set of options. |
| Change the random invalid rate                         | `invalid_rate` argument to `generate_random_data()`.            |
| Add a new generator                                    | a function in `test_generation.py`, with caching via `_cache.try_load_cache` and `_cache.save_cache`. |
| Extend the constraint language                         | `_TOKEN_REGEX`, `_ConstraintParser`, and `_eval_constraint` in `constraint.py`. |
| Change how a value is encoded for ACTS                 | `obj2acts`, `acts2obj`, and `_ACTS_ENUM_UNSAFE_CHARS` in `util.py`. |

## Standalone runs

Three modules have a `__main__` block:

- `python -m gemeaspy.tests.generator.test_generation <strength> [seed]` builds a small example spec and prints the resulting covering array and random suite side by side. Run this after changes to either generator as a sanity check.
- `python -m gemeaspy.tests.generator.constraint` parses a sample constraint and compares its evaluation against Python's own evaluation on random bindings. Run this after changes to the parser or evaluator.
- `python -m gemeaspy.tests.generator.parameter_spec` prints the auto-generated unused-task and unused-task-file constraints for visual inspection.

Cached suites live under `<repository>/test_data/input_cache/`. Deleting a file there forces regeneration on the next call.

## Further reading

The ACTS user guide (available in PDF format under `bin/ACTS/`) documents the command line options, configuration file format, supported algorithms, and the constraint and negative-testing features used here.
