import pytest

from gemeaspy.acquisition import main
from gemeaspy.tests import setup_config, setup_task_files
from gemeaspy.tests.terrameter_model import InstrumentServerEmulator
from gemeaspy.tests.test_case import AcquisitionTestCase


@pytest.fixture
def emulator():
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
    main.main([main.__file__] + task_files)
