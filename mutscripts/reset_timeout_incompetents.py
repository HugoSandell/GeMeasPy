"""Delete INCOMPETENT work results caused by timeouts from cosmic-ray databases."""
import glob
import sys
from pathlib import Path
from typing import cast

from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkResultStorage

_TIMEOUT_TAG = "CR:TIMEOUT"
_TIMEOUT_MARKER = "Acquisition timed out after"


def _is_timeout(output: str) -> bool:
    for line in output.splitlines():
        if line.lstrip("\r").startswith("E "):
            if _TIMEOUT_TAG in line or _TIMEOUT_MARKER in line:
                return True
    return False


def reset_timeout_incompetents(db_path: str) -> int:
    from sqlalchemy import select

    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        with db._session_maker.begin() as session:  # type: ignore[attr-defined]
            rows = (
                session.execute(
                    select(WorkResultStorage).where(
                        WorkResultStorage.test_outcome == TestOutcome.INCOMPETENT
                    )
                )
                .scalars()
                .all()
            )
            count = 0
            for row in rows:
                output = cast(str | None, row.output) or ""
                if _is_timeout(output):
                    session.delete(row)
                    count += 1
    return count


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        paths: list[str] = []
        for arg in argv[1:]:
            expanded = glob.glob(arg)
            if not expanded:
                print(f"Error: {arg!r} matches no files", file=sys.stderr)
                return 1
            paths.extend(expanded)
    else:
        paths = [str(p) for p in sorted(Path("test_data").glob("*.sqlite"))]

    if not paths:
        print("No databases found.", file=sys.stderr)
        return 1

    total = 0
    for db_path in paths:
        if not Path(db_path).exists():
            print(f"Error: {db_path!r} does not exist", file=sys.stderr)
            return 1
        count = reset_timeout_incompetents(db_path)
        print(f"{Path(db_path).name}: reset {count} timeout incompetent(s)")
        total += count

    if len(paths) > 1:
        print(f"Total: reset {total} timeout incompetent(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
