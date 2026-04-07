"""PyTest entry point for end-to-end testing of acquisition."""
import asyncio
import logging
import os
import sys
import time
from asyncio import subprocess

import pytest

from gemeaspy.settings import config as _config
from gemeaspy.tests import oracle, setup_config, setup_task_files
from gemeaspy.tests.oracle import OracleResult
from gemeaspy.tests.terrameter_model import InstrumentServerEmulator
from gemeaspy.tests.test_case import AcquisitionTestCase

ACQUISITION_TIMEOUT = 3 # The greatest amount of time to wait for acquisition to finish

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
async def test_main(test_case: AcquisitionTestCase, config, task_files):
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    env = {
        **os.environ,
        "TERRAMETER_PROJECTS_FOLDER": _config.TERRAMETER_PROJECTS_FOLDER,
        "LOCAL_PATH_TO_DATA": _config.LOCAL_PATH_TO_DATA,
        "TERRAMETER_CONNECTION_FILE": _config.TERRAMETER_CONNECTION_FILE,
    }
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
        stdout_bytes.decode(), stderr_bytes.decode(),
    )
    assert oracle_result.ok, oracle_result.msg