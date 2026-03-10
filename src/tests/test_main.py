import pytest

from acquisition import main
from tests import setup_config, setup_task_files


@pytest.fixture
def config(test_case):
    setup_config.setup(test_case)
    yield


@pytest.fixture
def task_files(test_case):
    yield setup_task_files.resolve_task_files(test_case)


def test_main(test_case, config, task_files):
    main.main([main.__file__] + task_files)
