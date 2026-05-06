"""PyTest entry point for end-to-end testing of acquisition."""

import asyncio
import logging
import os
import sys
from asyncio import subprocess

import pytest

from gemeaspy.settings import config as _config
from gemeaspy.tests import _logging, oracle, setup_config, setup_task_files
from gemeaspy.tests.generator.test_case import AcquisitionTestCase
from gemeaspy.tests.oracle import OracleResult
from gemeaspy.tests.terrameter_model import InstrumentServerEmulator
from gemeaspy.tests.terrameter_model.parameters import TerrameterMisbehavior, TerrameterProjectState
from gemeaspy.tests.terrameter_model.terrameter import TerrameterLS

# The greatest amount of time to wait for acquisition to finish
ACQUISITION_TIMEOUT = 10


@pytest.fixture
def emulator(test_case: AcquisitionTestCase):
    os.environ["USETERRAMETEREMULATOR"] = "1"
    instrument = InstrumentServerEmulator(
        misbehavior=TerrameterMisbehavior(test_case.parameters.emulator_misbehavior),
        suffix_project_name=test_case.parameters.emulator_suffix_project_name,
    )
    instrument.start()
    instrument.instrument.setup_project_state(
        TerrameterProjectState(test_case.parameters.emulator_project1_init_state),
        list(range(1, test_case.parameters.taskfile1_number_of_tasks + 1)),
    )
    instrument.instrument.setup_project_state(
        TerrameterProjectState(test_case.parameters.emulator_project2_init_state),
        list(range(1, test_case.parameters.taskfile2_number_of_tasks + 1)),
    )
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
async def test_main(test_case: AcquisitionTestCase, 
                    config, 
                    task_files, 
                    configure_default_port_handling, 
                    emulator: TerrameterLS):
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    env = {
        **os.environ,
        "TERRAMETER_PROJECTS_FOLDER": _config.TERRAMETER_PROJECTS_FOLDER,
        "LOCAL_PATH_TO_DATA": _config.LOCAL_PATH_TO_DATA,
        "TERRAMETER_CONNECTION_FILE": _config.TERRAMETER_CONNECTION_FILE,
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
        emulator
    )

    frame_str = ""
    if oracle_result.frame is not None:
        code = oracle_result.frame.f_code.co_code
        lineno = oracle_result.frame.f_lineno
        if code and lineno:
            frame_str = f"{oracle_result.frame.f_code.co_filename!r}, line {oracle_result.frame.f_lineno}"
            print(f"OracleResult @ {frame_str}")
    print("stdout:")
    print(stdout_bytes.decode(errors="replace"))
    print("stderr:")
    print(stderr_bytes.decode(errors="replace"))
    assert oracle_result.ok, f"{oracle_result.msg} ({frame_str})"