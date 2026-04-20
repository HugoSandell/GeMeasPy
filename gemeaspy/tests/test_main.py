"""PyTest entry point for end-to-end testing of acquisition."""

import asyncio
import logging
import os
import sys
from asyncio import subprocess

import pytest

from gemeaspy.settings import config as _config
from gemeaspy.tests.generator.constraint import Constraint
from gemeaspy.tests.generator.parameter_spec import ACQUISITION_CONSTRAINTS, AcquisitionParameterSpec
from gemeaspy.tests import _logging, oracle, setup_config, setup_task_files
from gemeaspy.tests.generator.test_case import AcquisitionTestCase
from gemeaspy.tests.oracle import OracleResult
from gemeaspy.tests.terrameter_model import InstrumentServerEmulator

# The greatest amount of time to wait for acquisition to finish
ACQUISITION_TIMEOUT = 10


@pytest.fixture
def emulator():
    os.environ["USETERRAMETEREMULATOR"] = "1"
    instrument = InstrumentServerEmulator()
    instrument.start()
    yield instrument
    instrument.stop()

@pytest.fixture
def config(test_case: AcquisitionTestCase, emulator):
    state = setup_config.ConfigState(test_case, emulator.address[1])
    yield state
    state.cleanup()

@pytest.fixture
def task_files(test_case: AcquisitionTestCase):
    task_files, cleanup = setup_task_files.resolve_task_files(test_case)
    yield task_files
    cleanup()

@pytest.mark.asyncio
async def test_main(test_case: AcquisitionTestCase, config, task_files, configure_default_port_handling):
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    env = {
        **os.environ,
        "TERRAMETER_PROJECTS_FOLDER": _config.TERRAMETER_PROJECTS_FOLDER,
        "LOCAL_PATH_TO_DATA": _config.LOCAL_PATH_TO_DATA,
        "TERRAMETER_CONNECTION_FILE": _config.TERRAMETER_CONNECTION_FILE,
        "TERRAMETER_EMULATOR_BEHAVIOR": test_case.parameters.emulator_behavior
    }
    _logging.info(f"Testing acquisition with parameters: {test_case}")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "gemeaspy.acquisition", *task_files,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=ACQUISITION_TIMEOUT
        )
    except asyncio.TimeoutError:
        proc.kill()
        pytest.fail(f"Acquisition timed out after {ACQUISITION_TIMEOUT}s")

    oracle_result: OracleResult = oracle.evaluate_test(
        test_case, config, task_files,
        stdout_bytes.decode(encoding="utf-8", errors="backslashreplace"), 
        stderr_bytes.decode(encoding="utf-8", errors="backslashreplace"),
    )
    
    print("num_args: ", test_case.parameters.num_args)
    print("arg_taskfile1: ", test_case.parameters.arg_taskfile1)
    print("arg_taskfile2: ", test_case.parameters.arg_taskfile2)
    print("taskfile1_number_of_tasks_error: ", test_case.parameters.taskfile1_number_of_tasks_error)
    print("taskfile2_number_of_tasks_error: ", test_case.parameters.taskfile2_number_of_tasks_error)
    print("task files: ", task_files)
    
    print("Test constraint:")
    test_constraint = Constraint(f'num_args < 2 || arg_taskfile2 = "__INVALID_TASKFILE2__"  => taskfile2_number_of_tasks_error = "CORRECT"')
    print(test_constraint)
    print("Success:", test_constraint.test({"num_args": 1, "arg_taskfile1": "__VALID_TASKFILE1__", "arg_taskfile2": "__VALID_TASKFILE2__", "taskfile2_number_of_tasks_error":  "MINUS_1"}))

    
    frame_str = ""
    if oracle_result.frame is not None:
        code = oracle_result.frame.f_code.co_code
        lineno = oracle_result.frame.f_lineno
        if code and lineno:
            frame_str = f"{oracle_result.frame.f_code.co_filename!r}, line {oracle_result.frame.f_lineno}"
            print(f"OracleResult @ {frame_str}")
            
    assert oracle_result.ok, f"{oracle_result.msg} ({frame_str})"