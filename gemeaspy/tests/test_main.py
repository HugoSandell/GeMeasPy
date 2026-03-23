"""PyTest entry point for end-to-end testing of acquisition."""
from contextlib import nullcontext
from concurrent import futures
import os

from coverage import debug
import pytest

from gemeaspy.acquisition import run_acquisition
from gemeaspy.acquisition.main import __file__ as main_file_path
from gemeaspy.tests import exception_checks, setup_config, setup_task_files
from gemeaspy.tests.terrameter_model import InstrumentServerEmulator
from gemeaspy.tests.test_case import AcquisitionTestCase
from gemeaspy.tests import _logging

ACQUISITION_TIMEOUT = 10.0 # The greatest amount of time to wait for acquisition to finish

@pytest.fixture
def emulator():
    os.environ["USETERRAMETEREMULATOR"] = "1"
    instrument = InstrumentServerEmulator()
    instrument.start()
    yield instrument
    instrument.stop()


@pytest.fixture
def config(test_case: AcquisitionTestCase, emulator):
    cleanup = setup_config.setup(test_case, emulator.address[1])
    yield
    cleanup()

@pytest.fixture
def task_files(test_case: AcquisitionTestCase):
    task_files, cleanup = setup_task_files.resolve_task_files(test_case)
    yield task_files
    cleanup()
    

def test_main(test_case: AcquisitionTestCase, config, task_files):
    executor = futures.ThreadPoolExecutor(max_workers=1)
        
    #with exception_checks.check_exception(test_case): 
    try:
        future = executor.submit(run_acquisition, [main_file_path] + task_files)
        try: 
            future.result(timeout=10)
        except futures.TimeoutError as e:
            pytest.fail("Call timed out")
    except Exception as e:
        if test_case.expect_failure:
            _logging.warning("Raised exception: " + str(type(e)))
        else:
            raise