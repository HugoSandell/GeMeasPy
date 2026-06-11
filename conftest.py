"""Configuration and setup for pytest"""

import os
import socket
from functools import reduce

import paramiko
import pytest

from gemeaspy.tests import oracle
from gemeaspy.tests.generator import test_generation
from gemeaspy.tests.generator.parameter_spec import (
    ACQUISITION_CONSTRAINTS,
    ACQUISITION_PARAM_SPEC,
    VALID_HOSTNAME,
)
from gemeaspy.tests.generator.test_case import TestCase
from gemeaspy.tests.oracle import Port22Status
from gemeaspy.tests.terrameter_model.parameters import TerrameterProjectState


def _detect_port22_status() -> Port22Status:
    """Probe port 22 on the test host once and classify what is running there."""
    host = VALID_HOSTNAME  # "127.0.0.1"
    port = 22

    # Quick TCP reachability check first
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except (ConnectionRefusedError, socket.timeout, OSError):
        return Port22Status.CLOSED

    # Port is open - attempt SSH.  Try every valid (username, password) pair
    # that the test suite would ever use.  Username is hardcoded in
    # setup_config._create_connection_settings; valid passwords come from the
    # parameter spec.
    test_username = "root"
    # VALID_PORT sentinel is resolved to the emulator port at runtime; skip it.
    valid_passwords: list[str] = [
        p for p in ACQUISITION_PARAM_SPEC["connection_password"][0]
        if isinstance(p, str)
    ]

    for password in valid_passwords:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                hostname=host,
                port=port,
                username=test_username,
                password=password,
                allow_agent=False,
                look_for_keys=False,
                timeout=2,
            )
            ssh.close()
            return Port22Status.SSH_OPEN
        except paramiko.AuthenticationException:
            return Port22Status.SSH_AUTH_REQUIRED
        except paramiko.SSHException:
            return Port22Status.NON_SSH
        except Exception:
            return Port22Status.CLOSED

    return Port22Status.SSH_AUTH_REQUIRED


@pytest.fixture(scope="session")
def configure_default_port_handling():
    """Probe port 22 once and configure the oracle accordingly.

    * If an SSH server on port 22 accepts any valid test credential, the whole
      session is aborted - that would allow the SUT to connect successfully on
      tests that expect a failure.
    * If SSH is up but rejects credentials, the oracle is told to expect an
      authentication error instead of a network error.
    * If port 22 is closed or runs a non-SSH service, the oracle keeps its
      default expectation ("Could not reach the server" /
      "Could not establish an SSH session").
    """
    status = _detect_port22_status()

    if status == Port22Status.SSH_OPEN:
        pytest.fail(
            "An SSH service on port 22 is accepting connections with the test "
            "credentials (username='root', password=''). "
            "Stop the SSH service on port 22 before running the tests."
        )

    oracle.port22_status = status
    yield
    oracle.port22_status = Port22Status.CLOSED  # restore default

@pytest.fixture(autouse=True)
def environment_variable_debug():
    os.environ["DEBUG"] = "1"

def pytest_addoption(parser: pytest.Parser):
    parser.addoption("--generator", "-G", dest="generator", type=str, default="acts", 
                     help="Specify which test case generator to use ('random' or 'acts')")
    parser.addoption("--size", "-N", dest="size", default=100, type=int, 
                     help="Specify the number of test cases. (random only)")
    parser.addoption("--strength", "-T", dest="strength", default=3, type=int, 
                     help="Specify the test suite interaction strength. (ACTS only)")
    parser.addoption("--seed", "-S", dest="seed", default=None, type=int,
                     help="Specify the random seed. (random only)")
    parser.addoption("--n-valid", dest="n_valid", default=None, type=int,
                     help="Limit the number of valid test cases. Matches the valid/invalid ratio of a paired ACTS suite. (random only)")


def _mark_test_case(test_case: TestCase):
    if (
        not test_case.expect_failure
        and test_case["taskfile1_number_of_tasks"] != 0
        and test_case["emulator_project1_init_state"]
        == TerrameterProjectState.UNINITIALISED
        and test_case["emulator_project2_init_state"]
        in (
            TerrameterProjectState.MEASURING,
            TerrameterProjectState.ONE_DONE,
            TerrameterProjectState.ALL_DONE,
        )
    ):
        return pytest.param(
            test_case,
            marks=pytest.mark.xfail(
                reason="Program is unable to detect whether an interrupted "
                "project corresponds to the active task file."
            ),
        )

    return test_case


def pytest_generate_tests(metafunc: pytest.Metafunc):
    if "test_case" not in metafunc.fixturenames:
        return
    t = metafunc.config.getoption("strength")
    N = metafunc.config.getoption("size")
    random_seed = metafunc.config.getoption("seed")
    generator_name = str(metafunc.config.getoption("generator")).lower().strip()
    
    if generator_name == "acts":
        if t <= 0:
            raise ValueError("Interaction strength must be greater than 0")
        elif t > len(ACQUISITION_PARAM_SPEC):
            raise ValueError(f"Interaction strength must not be greater than {len(ACQUISITION_PARAM_SPEC)}")
        test_data = test_generation.generate_covering_array(param_spec=ACQUISITION_PARAM_SPEC, constraints=ACQUISITION_CONSTRAINTS, strength=t)
    elif generator_name == "random":
        max_N: int = reduce(lambda x, p: x * len(ACQUISITION_PARAM_SPEC[p]), ACQUISITION_PARAM_SPEC, 1)
        if N <= 0:
            raise ValueError("Test suite size must be greater than 0")
        if N > max_N:
            raise ValueError(f"Test suite size must not be greater than {max_N}")    
        n_valid_target = metafunc.config.getoption("n_valid")
        test_data = test_generation.generate_random_data(param_spec=ACQUISITION_PARAM_SPEC, constraints=ACQUISITION_CONSTRAINTS, case_count=N, seed=random_seed, n_valid=n_valid_target)
    else:
        raise ValueError(f"'{generator_name}' is not a valid test case generator.")
    metafunc.parametrize("test_case", map(_mark_test_case, test_data))
