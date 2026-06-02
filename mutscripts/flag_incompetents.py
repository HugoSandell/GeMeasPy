"""Reclassify KILLED/SURVIVED work items as INCOMPETENT in cosmic-ray databases.

Uses only the E-prefixed lines from pytest failure output so that source code is ignored.

Usage:
    python flag_incompetents.py [<db_path> ...]
    python flag_incompetents.py # scans all test_data/*.sqlite
"""
import sys
import warnings
from pathlib import Path
from typing import cast

from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkResultStorage

# Machine-readable tags written by test_main.py (current databases)
_TIMEOUT_TAG = "CR:TIMEOUT"
_VALID_FAIL_TAG = "CR:VALID_FAIL"
_INVALID_FAIL_TAG = "CR:INVALID_FAIL"

# Text-based fallbacks for databases produced before the CR: tags were introduced
_TIMEOUT_MARKER = "Acquisition timed out after"
_INVALID_CASE_MARKER = "for invalid "
_DATA_MODIFICATION_MARKER = "SUT modified file configured as LOCAL_PATH_TO_DATA"

# Oracle messages that prove the SUT ran and produced specific output - fallback
# for old databases that predate CR:VALID_FAIL tagging.
_REAL_KILL_MARKERS = (
    # _evaluate_transfer_valid
    "Could not find any project files on Terrameter emulator",
    "Directory that should have been transferred not found locally",
    "Project file that should have been transferred was not found locally",
    "project files to be transferred, but found",
    "Content mismatch for transferred file",
    # _evaluate_emulator_valid
    "Test case was configured to add '_#' suffix",
    "projects to be created on emulator, but found",
    "tasks to be created for taskfile",
    "task rows in project",
    "task name starting with",
)


def _error_lines(output: str) -> str:
    return "\n".join(
        line.rstrip("\r")
        for line in output.splitlines()
        if line.lstrip("\r").startswith("E ")
    )


def _get_mutated_code(mutation, root_dir: Path) -> str | None:
    import cosmic_ray.plugins
    from cosmic_ray.mutating import mutate_code
    from cosmic_ray.util import read_python_source

    module_path = root_dir / mutation.module_path
    if not module_path.is_file():
        return None
    try:
        operator_class = cosmic_ray.plugins.get_operator(mutation.operator_name)
        try:
            operator_args = mutation.operator_args
        except AttributeError:
            operator_args = {}
        operator = operator_class(**operator_args)
        return mutate_code(read_python_source(module_path), operator, mutation.occurrence)
    except Exception:
        return None


def reclassify_db(db_path: str) -> tuple[int, int, int]:
    """Reclassify results in db_path as INCOMPETENT where appropriate.
    Returns (timeout_count, syntax_error_count, valid_case_count).
    """
    from sqlalchemy import select

    root_dir = Path(db_path).resolve().parent.parent

    # compile-check to find syntax-error job_ids (covers KILLED and SURVIVED).
    syntax_error_ids: set[str] = set()
    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        for work_item, result in db.completed_work_items:
            if result.test_outcome not in (TestOutcome.KILLED, TestOutcome.SURVIVED):
                continue
            for mutation in work_item.mutations:
                mutated_code = _get_mutated_code(mutation, root_dir)
                if mutated_code is None:
                    continue
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", SyntaxWarning)
                        compile(mutated_code, str(root_dir / mutation.module_path), "exec")
                except SyntaxError:
                    syntax_error_ids.add(work_item.job_id)
                    break

    # apply all reclassifications in a single session.
    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        with db._session_maker.begin() as session:  # type: ignore[attr-defined]
            syntax_error_count = 0
            if syntax_error_ids:
                syntax_rows = (
                    session.execute(
                        select(WorkResultStorage).where(
                            WorkResultStorage.job_id.in_(syntax_error_ids)
                        )
                    )
                    .scalars()
                    .all()
                )
                syntax_error_count = len(syntax_rows)
                for row in syntax_rows:
                    row.test_outcome = TestOutcome.INCOMPETENT  # type: ignore[assignment]

            killed_rows = (
                session.execute(
                    select(WorkResultStorage).where(
                        WorkResultStorage.test_outcome == TestOutcome.KILLED
                    )
                )
                .scalars()
                .all()
            )
            timeout_count = 0
            valid_case_count = 0
            for row in killed_rows:
                if row.job_id in syntax_error_ids:
                    continue
                output = cast(str | None, row.output) or ""
                errors = _error_lines(output)
                # Check CR: tags first (current databases), then fall back for databases that predate the tags.
                if _TIMEOUT_TAG in errors or _TIMEOUT_MARKER in errors:
                    row.test_outcome = TestOutcome.INCOMPETENT  # type: ignore[assignment]
                    timeout_count += 1
                elif _VALID_FAIL_TAG in errors or _INVALID_FAIL_TAG in errors:
                    pass  # tagged as a real oracle kill - keep KILLED
                elif (
                    _INVALID_CASE_MARKER not in errors
                    and _DATA_MODIFICATION_MARKER not in errors
                    and not any(m in errors for m in _REAL_KILL_MARKERS)
                ):
                    row.test_outcome = TestOutcome.INCOMPETENT  # type: ignore[assignment]
                    valid_case_count += 1

    return timeout_count, syntax_error_count, valid_case_count


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        db_paths = [Path(p) for p in argv[1:]]
    else:
        db_paths = sorted(Path("test_data").glob("*.sqlite"))

    if not db_paths:
        print("No databases found.", file=sys.stderr)
        return 1

    total_timeout = 0
    total_syntax = 0
    total_valid = 0
    for db_path in db_paths:
        if not db_path.exists():
            print(f"Error: {db_path!r} does not exist", file=sys.stderr)
            return 1
        timeout_count, syntax_error_count, valid_case_count = reclassify_db(str(db_path))
        total = timeout_count + syntax_error_count + valid_case_count
        parts = []
        if timeout_count:
            parts.append(f"{timeout_count} timeout")
        if syntax_error_count:
            parts.append(f"{syntax_error_count} syntax error")
        if valid_case_count:
            parts.append(f"{valid_case_count} valid-case error/exception")
        detail = f" ({', '.join(parts)})" if parts else ""
        print(f"{db_path.name}: reclassified {total} kill(s) as incompetent{detail}")
        total_timeout += timeout_count
        total_syntax += syntax_error_count
        total_valid += valid_case_count

    if len(db_paths) > 1:
        total = total_timeout + total_syntax + total_valid
        parts = []
        if total_timeout:
            parts.append(f"{total_timeout} timeout")
        if total_syntax:
            parts.append(f"{total_syntax} syntax error")
        if total_valid:
            parts.append(f"{total_valid} valid-case error/exception")
        detail = f" ({', '.join(parts)})" if parts else ""
        print(f"Total: reclassified {total} kill(s) as incompetent{detail}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
