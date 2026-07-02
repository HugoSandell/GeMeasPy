import itertools
import random
from typing import TypeAlias

from gemeaspy.tests import _logging
from gemeaspy.tests.generator import _cache
from gemeaspy.tests.generator.constraint import Constraint
from gemeaspy.tests.generator.parameter_spec import ParameterSpec
from gemeaspy.tests.generator.test_case import TestCase

def _max_valid_cases(param_spec: ParameterSpec, constraints: list[Constraint]):
    param_names = list(param_spec)
    param_valid_values = [param_spec[p][0] for p in param_names]
    return sum(
        1 for combination in itertools.product(*param_valid_values)
        if all(c.test(dict(zip(param_names, combination))) for c in constraints)
    )


def _resolve_invalid(
    param_spec: ParameterSpec,
    constraints: list[Constraint],
    invalid_param: str,
    invalid_value,
    starting_params: dict,
) -> dict | None:
    """Return a parameter dict with invalid_param=invalid_value satisfying all constraints."""
    param_names = list(param_spec)
    params = dict(starting_params)
    params[invalid_param] = invalid_value

    for _ in range(len(constraints) * len(param_names) + 1):
        violated = [c for c in constraints if not c.test(params)]
        if not violated:
            return params
        for constraint in violated:
            for p in constraint.parameters:
                if p == invalid_param:
                    continue
                for v in param_spec[p][0]:
                    params[p] = v
                    if constraint.test(params):
                        break
                else:
                    # no single valid value for p fixed this constraint alone; leave it
                    # at whichever value we ended on and let the next iteration retry
                    pass
                break  # try only the first adjustable parameter per constraint per pass

    return params if all(c.test(params) for c in constraints) else None


def _build_invalid_case(param_spec: ParameterSpec, param_names: list[str], params: dict, invalid_param: str) -> TestCase:
    case = param_spec.TestCaseType()
    for p in param_names:
        case.parameters[p] = params[p]
    case.invalid_parameter = invalid_param
    case.expect_failure = True
    return case


def _generate_base_choice_invalid_cases(
    param_spec: ParameterSpec,
    constraints: list[Constraint],
) -> list[TestCase]:
    """Generate exactly one test case per unique (invalid_param, invalid_value) pair.
    Mirrors how ACTS handles <invalidValues> at strength=1: each invalid value is paired
    with the first satisfying valid value for every other parameter.
    """
    param_names = list(param_spec)
    results: list[TestCase] = []
    for invalid_param in param_spec:
        for invalid_value in param_spec[invalid_param][1]:
            starting = {p: param_spec[p][0][0] for p in param_names}
            params = _resolve_invalid(param_spec, constraints, invalid_param, invalid_value, starting)
            if params is None:
                _logging.warning(
                    f"Could not resolve base-choice test case for "
                    f"{invalid_param}={invalid_value!r}; skipping."
                )
                continue
            results.append(_build_invalid_case(param_spec, param_names, params, invalid_param))
    return results


def _generate_overflow_invalid_cases(
    param_spec: ParameterSpec,
    constraints: list[Constraint],
    seen_keys: set[tuple],
    n_needed: int,
) -> list[TestCase]:
    """Generate additional invalid cases with random starting params.
    Used when more invalid cases are needed beyond base-choice to fill the requested suite size.
    """
    param_names = list(param_spec)
    invalid_pairs = [(p, v) for p in param_names for v in param_spec[p][1]]
    results: list[TestCase] = []
    max_attempts = n_needed * 200

    for _ in range(max_attempts):
        if len(results) >= n_needed:
            break
        invalid_param, invalid_value = random.choice(invalid_pairs)
        starting = {p: random.choice(param_spec[p][0]) for p in param_names}
        params = _resolve_invalid(param_spec, constraints, invalid_param, invalid_value, starting)
        if params is None:
            continue
        key = tuple(params[p] for p in param_names)
        if key in seen_keys:
            continue
        results.append(_build_invalid_case(param_spec, param_names, params, invalid_param))
        seen_keys.add(key)

    if len(results) < n_needed:
        _logging.warning(
            f"Overflow invalid generator: requested {n_needed} cases but only "
            f"{len(results)} unique cases available."
        )
    return results


RNGSeed: TypeAlias = None | int | str
def generate_random_data(param_spec: ParameterSpec, constraints: list[Constraint], case_count: int, seed: RNGSeed = None, n_valid: int | None = None) -> list[TestCase]:
    """Generate a test suite of exactly case_count cases.

    Always starts with one base-choice case per (invalid_param, invalid_value) pair, then fills
    remaining invalid slots via random overflow (seeded, so seeds produce different suites), then
    fills valid slots up to n_valid (or all available valid combos if n_valid is None).
    Pass n_valid=<acts_valid_count> to match the valid/invalid ratio of a paired ACTS suite.
    """
    seed_repr: str = str(seed)
    if seed is None:
        seed = random.getrandbits(64)
    if isinstance(seed, int):
        seed_repr = f"{seed:x}"
    elif isinstance(seed, str):
        seed_repr = seed.encode().hex()

    # n_valid and _bc suffix are part of cache key so suites with different ratios/logic don't collide
    v_tag = f"_v{n_valid}" if n_valid is not None else ""
    cache_tag = f"n{case_count}{v_tag}_s{seed_repr}_bc"
    cache = _cache.try_load_cache(param_spec, constraints, cache_tag)
    if cache is not None:
        return cache

    random.seed(seed)

    _logging.debug("Random test case generator starting.")

    param_names = list(param_spec)

    # Phase 1: one base-choice test case per unique (invalid_param, invalid_value) pair
    base_invalid = _generate_base_choice_invalid_cases(param_spec, constraints)

    # Deduplicate and build seen-keys set for O(1) dup checks
    seen_keys: set[tuple] = set()
    deduplicated: list[TestCase] = []
    for case in base_invalid:
        key = tuple(case.parameters[p] for p in param_names)
        if key not in seen_keys:
            deduplicated.append(case)
            seen_keys.add(key)
    base_invalid = deduplicated

    # Phase 2: valid cases, capped at n_valid (matches ACTS valid count when provided)
    max_case_count_valid = _max_valid_cases(param_spec, constraints)
    valid_target = min(n_valid, max_case_count_valid) if n_valid is not None else max_case_count_valid
    n_valid_needed = max(0, min(case_count - len(base_invalid), valid_target))
    valid_cases: list[TestCase] = []
    generated_valid = 0
    while generated_valid < n_valid_needed:
        case = param_spec.TestCaseType()
        for p in param_names:
            case.parameters[p] = random.choice(param_spec[p][0])
        if not all(c.test(case.parameters) for c in constraints):
            continue
        key = tuple(case.parameters[p] for p in param_names)
        if key in seen_keys:
            continue
        case.expect_failure = False
        case.invalid_parameter = None
        valid_cases.append(case)
        seen_keys.add(key)
        generated_valid += 1

    # Phase 3: random overflow invalid cases to fill the rest of case_count
    # These vary by seed, giving each seed a distinct set of invalid combinations to explore.
    n_overflow = max(0, case_count - len(base_invalid) - len(valid_cases))
    overflow_invalid: list[TestCase] = []
    if n_overflow > 0:
        overflow_invalid = _generate_overflow_invalid_cases(
            param_spec, constraints, seen_keys, n_overflow
        )

    test_data = base_invalid + valid_cases + overflow_invalid
    test_data = test_data[:case_count]

    # Verify uniqueness
    keys = [tuple(c.parameters[p] for p in param_names) for c in test_data]
    assert len(keys) == len(set(keys)), "Duplicate test cases detected"

    # Verify against constraints
    for case in test_data:
        for constraint in constraints:
            if not constraint.test(case.parameters):
                rows = [f'{p} = {case[p]!r}' for p in constraint.parameters]
                _logging.error(
                    f"Random generator output violated constraint.\n"
                    f"Parameters:\n{chr(10).join(rows)}\nConstraint: {constraint!r}"
                )
                raise RuntimeError(f"Random generator violated constraint. See {_logging.file_path}")

    _logging.debug(f"Random test case generation finished. {len(test_data)} cases generated.")
    _cache.save_cache(test_data, param_spec, constraints, cache_tag)
    return test_data
