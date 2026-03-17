"""PyTest entry point for end-to-end testing of acquisition."""
import os

import pytest

from gemeaspy.acquisition import run_acquisition
from gemeaspy.acquisition.main import __file__ as main_file_path
from gemeaspy.tests import exception_checks, setup_config, setup_task_files
from gemeaspy.tests.terrameter_model import InstrumentServerEmulator
from gemeaspy.tests.test_case import AcquisitionTestCase


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
    with exception_checks.check_exception(test_case):
        run_acquisition([main_file_path] + task_files)
