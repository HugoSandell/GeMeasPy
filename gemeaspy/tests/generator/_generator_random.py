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
    """Return a parameter dict with invalid_param=invalid_value satisfying all constraints.
    """
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


def _generate_sweep_invalid_cases(
    param_spec: ParameterSpec,
    constraints: list[Constraint],
    seen_keys: set[tuple],
    n_needed: int,
) -> list[TestCase]:
    """Generate additional invalid cases by sweeping through valid values of each parameter.
    """
    param_names = list(param_spec)
    max_sweep = max(len(param_spec[p][0]) for p in param_names)
    results: list[TestCase] = []

    for sweep in range(1, max_sweep):
        if len(results) >= n_needed:
            break
        for invalid_param in param_spec:
            for invalid_value in param_spec[invalid_param][1]:
                if len(results) >= n_needed:
                    break
                starting = {p: param_spec[p][0][sweep % len(param_spec[p][0])] for p in param_names}
                params = _resolve_invalid(param_spec, constraints, invalid_param, invalid_value, starting)
                if params is None:
                    continue
                key = tuple(params[p] for p in param_names)
                if key in seen_keys:
                    continue
                results.append(_build_invalid_case(param_spec, param_names, params, invalid_param))
                seen_keys.add(key)

    return results


def _generate_overflow_invalid_cases(
    param_spec: ParameterSpec,
    constraints: list[Constraint],
    seen_keys: set[tuple],
    n_needed: int,
) -> list[TestCase]:
    """Generate additional invalid cases with random starting params.
    Used when the deterministic sweep cases are exhausted but the requested suite size is not yet reached.
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
    """Generate a random test suite of exactly case_count cases.
    """
    # Assign a fixed seed to None to make caching more meaningful
    seed_repr: str = str(seed)
    if seed is None:
        seed = random.getrandbits(64)
    if isinstance(seed, int):
        seed_repr = f"{seed:x}"
    elif isinstance(seed, str):
        seed_repr = seed.encode().hex()

    # Check cache - n_valid is part of the key so suites with different ratios don't collide
    v_tag = f"_v{n_valid}" if n_valid is not None else ""
    cache_tag = f"n{case_count}{v_tag}_s{seed_repr}"
    cache = _cache.try_load_cache(param_spec, constraints, cache_tag)
    if cache is not None:
        return cache

    random.seed(seed)

    _logging.debug("Random test case generator starting.")

    param_names = list(param_spec)

    # Phase 1: one base-choice test case per unique invalid value (ACTS strength=1 style)
    base_invalid = _generate_base_choice_invalid_cases(param_spec, constraints)

    # Deduplicate and build the seen-keys set for O(1) dup checks
    seen_keys: set[tuple] = set()
    deduplicated: list[TestCase] = []
    for case in base_invalid:
        key = tuple(case.parameters[p] for p in param_names)
        if key not in seen_keys:
            deduplicated.append(case)
            seen_keys.add(key)
    base_invalid = deduplicated

    max_case_count_valid = _max_valid_cases(param_spec, constraints)
    # Cap valid cases at n_valid when provided (matches ratio of the corresponding ACTS suite)
    valid_target = min(n_valid, max_case_count_valid) if n_valid is not None else max_case_count_valid

    # Phase 2 (large suites only): sweep-based invalid cases to extend pairwise coverage.
    # Only needed when case_count exceeds what base_invalid + target valid cases can fill.
    # Mirrors how ACTS strength=2 includes invalid values in its pairwise matrix.
    n_sweep_needed = max(0, case_count - len(base_invalid) - valid_target)
    sweep_invalid: list[TestCase] = []
    if n_sweep_needed > 0:
        sweep_invalid = _generate_sweep_invalid_cases(
            param_spec, constraints, seen_keys, n_sweep_needed
        )

    all_invalid = base_invalid + sweep_invalid

    # Phase 3: fill up to valid_target slots with random valid cases
    n_valid_needed = max(0, min(case_count - len(all_invalid), valid_target))
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

    # Phase 4 (overflow only): random invalid cases to exactly reach case_count when the
    # deterministic phases (sweep + valid) cannot fill the full request.
    n_overflow = max(0, case_count - len(all_invalid) - len(valid_cases))
    overflow_invalid: list[TestCase] = []
    if n_overflow > 0:
        overflow_invalid = _generate_overflow_invalid_cases(
            param_spec, constraints, seen_keys, n_overflow
        )

    test_data = all_invalid + valid_cases + overflow_invalid
    # Trim to requested size (only needed if overflow couldn't fill the last slots)
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
