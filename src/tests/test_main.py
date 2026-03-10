from acquisition import main
from tests import setup_config, setup_task_files


def test_main(test_case):
    setup_config.setup(test_case)
    main.main([main.__file__] + setup_task_files.resolve_task_files(test_case))
