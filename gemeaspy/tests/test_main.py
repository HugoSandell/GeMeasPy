"""PyTest entry point for end-to-end testing of acquisition."""
import os
from concurrent import futures

import pytest

from gemeaspy.acquisition import run_acquisition
from gemeaspy.acquisition.main import __file__ as main_file_path
from gemeaspy.tests import (_logging, exception_checks, oracle, setup_config,
                            setup_task_files)
from gemeaspy.tests.oracle import OracleResult
from gemeaspy.tests.terrameter_model import InstrumentServerEmulator
from gemeaspy.tests.test_case import AcquisitionTestCase

ACQUISITION_TIMEOUT = 3.0 # The greatest amount of time to wait for acquisition to finish

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
    yield
    state.cleanup()

@pytest.fixture
def task_files(test_case: AcquisitionTestCase):
    task_files, cleanup = setup_task_files.resolve_task_files(test_case)
    yield task_files
    cleanup()
    

def test_main(test_case: AcquisitionTestCase, config, task_files, capfd: pytest.CaptureFixture):
    executor = futures.ThreadPoolExecutor(max_workers=1)
        
    #with exception_checks.check_exception(test_case): 

    future = executor.submit(run_acquisition, [main_file_path] + task_files)
    try: 
        future.result(timeout=ACQUISITION_TIMEOUT)
    except futures.TimeoutError as e:
        pytest.fail("Call timed out")
        
    capture = capfd.readouterr()
    oracle_result: OracleResult = oracle.evaluate_test(test_case, task_files, capture.out, capture.err)
    assert oracle_result.ok, oracle_result.msg