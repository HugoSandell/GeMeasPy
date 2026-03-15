import re
from contextlib import nullcontext
from re import Pattern

import pytest

from gemeaspy.tests import parameter_spec
from gemeaspy.tests.test_case import AcquisitionTestCase


class ExceptionCheck:
    expected_exception: type[BaseException] | tuple[type[BaseException], ...] | None
    match_pattern: Pattern[str] | None

    def __init__(
        self,
        expected_exception: type[BaseException]
        | tuple[type[BaseException], ...]
        | None = None,
        match: str | Pattern[str] | None = None,
    ):
        self.expected_exception = expected_exception
        if isinstance(match, str):
            match = re.compile(match)
        self.match_pattern = match

    def matches(self, exc: BaseException) -> bool:
        return (
            self.expected_exception is None or isinstance(exc, self.expected_exception)
        ) and (
            self.match_pattern is None or re.search(self.match_pattern, str(exc)) is not None
        )


NO_TASK_FILES_CHECK = ExceptionCheck(match="No task file provided")
FILE_NOT_FOUND_CHECK = ExceptionCheck(FileNotFoundError)


def check_exception(test_case: AcquisitionTestCase):
    exception_checks = []

    if len(test_case.arg_task_files) == 0:
        exception_checks.append(NO_TASK_FILES_CHECK)

    if any(
        f in ("", parameter_spec.INVALID_FILE) for f in test_case.arg_task_files
    ) or parameter_spec.INVALID_FILE in (
        test_case.config_local_data_path,
        test_case.config_connection_file,
    ):
        exception_checks.append(FILE_NOT_FOUND_CHECK)

    if len(exception_checks) == 0:
        # this test case should not raise an exception
        return nullcontext()

    # `expected_exception` and `match` arguments are redundant with `check` but
    # can improve the error messages for failing tests.

    if any(c.expected_exception is None for c in exception_checks):
        expected_exception = tuple()
    else:
        expected_exception = tuple({c.expected_exception for c in exception_checks})

    if any(c.match_pattern is None for c in exception_checks):
        match_pattern = None
    else:
        match_pattern = "|".join(c.match_pattern.pattern for c in exception_checks)

    return pytest.raises(
        expected_exception,
        match=match_pattern,
        check=lambda e: any(c.matches(e) for c in exception_checks),
    )
