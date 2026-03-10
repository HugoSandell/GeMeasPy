import pytest

from acquisition import main
from tests import setup_config, setup_task_files


@pytest.fixture
def config(test_case):
    cleanup = setup_config.setup(test_case)
    yield
    cleanup()


@pytest.fixture
def task_files(test_case):
    task_files, cleanup = setup_task_files.resolve_task_files(test_case)
    yield task_files
    cleanup()


def test_main(test_case, config, task_files):
    main.main([main.__file__] + task_files)
