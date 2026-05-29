"""Reset work items killed by test failures known to be caused by problems with the execution environment."""
import glob
import sys
from pathlib import Path

from cosmic_ray import work_db
from cosmic_ray.work_db import WorkDB, WorkResultStorage

# These were determined by examining test outputs, particularly for falsely killed Equivalent mutants.
_SPURIOUS_MARKERS = [
    "Failed: Acquisition timed out after", # Timeouts due to e.g. insufficient resource
    "MemoryError",                         # Issues with system memory
]

def reset_spurious_kills(db_path: str) -> int:
    from sqlalchemy import or_, select

    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        with db._session_maker.begin() as session:  # type: ignore[attr-defined]
            rows = (
                session.execute(
                    select(WorkResultStorage).where(
                        or_(*(WorkResultStorage.output.contains(m) for m in _SPURIOUS_MARKERS))
                    )
                )
                .scalars()
                .all()
            )
            count = len(rows)
            for row in rows:
                session.delete(row)
    return count


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(f"Usage: {argv[0]} <db_path> [<db_path> ...]", file=sys.stderr)
        return 1

    paths: list[str] = []
    for arg in argv[1:]:
        expanded = glob.glob(arg)
        if not expanded:
            print(f"Error: {arg!r} matches no files", file=sys.stderr)
            return 1
        paths.extend(expanded)

    total = 0
    for db_path in paths:
        if not Path(db_path).exists():
            print(f"Error: {db_path!r} does not exist", file=sys.stderr)
            return 1
        count = reset_spurious_kills(db_path)
        print(f"{db_path}: reset {count} item(s)")
        total += count

    if len(paths) > 1:
        print(f"Total: reset {total} item(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
