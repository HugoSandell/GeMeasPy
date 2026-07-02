"""Delete all INCOMPETENT work results from cosmic-ray databases."""
import glob
import sys
from pathlib import Path
from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkResultStorage


def reset_incompetents(db_path: str) -> int:
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
            count = len(rows)
            for row in rows:
                session.delete(row)
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
        count = reset_incompetents(db_path)
        print(f"{Path(db_path).name}: reset {count} incompetent(s)")
        total += count

    if len(paths) > 1:
        print(f"Total: reset {total} incompetent(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
