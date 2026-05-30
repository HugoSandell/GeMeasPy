"""Reset work items killed by test failures known to be caused by problems with the execution environment."""
import glob
import json
import sys
from pathlib import Path

from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkResultStorage

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


def _load_coverage_lines(coverage_json: Path) -> dict[str, set[int]]:
    if not coverage_json.is_file():
        return {}
    with open(coverage_json, encoding="utf-8") as f:
        cov_data = json.load(f)
    covered: dict[str, set[int]] = {}
    for filepath, file_data in cov_data.get("files", {}).items():
        covered[str(Path(filepath).resolve())] = set(file_data.get("executed_lines", []))
    return covered

def _is_covered(module_path: str, line: int, covered: dict[str, set[int]], root: Path) -> bool:
    module_abs = str((root / module_path).resolve())
    return module_abs in covered and line in covered[module_abs]

def reset_uncovered_killed(db_path: str) -> int:
    db_file = Path(db_path)
    data_dir = db_file.parent
    root = data_dir.parent
    coverage_json = data_dir / f"baseline_{db_file.stem.removeprefix('cosmicray_')}_coverage.json"

    covered = _load_coverage_lines(coverage_json)
    if not covered:
        return 0

    to_reset: list[str] = []
    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        for work_item, result in db.completed_work_items:
            if result.test_outcome != TestOutcome.KILLED:
                continue
            for mutation in work_item.mutations:
                if not _is_covered(str(mutation.module_path), mutation.start_pos[0], covered, root):
                    print(f"  WARNING: {db_file.name}: job {work_item.job_id} mutant at "
                          f"{mutation.module_path}:{mutation.start_pos[0]} is uncovered but KILLED - resetting")
                    to_reset.append(work_item.job_id)
                    break

    if not to_reset:
        return 0

    from sqlalchemy import select
    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        with db._session_maker.begin() as session:  # type: ignore[attr-defined]
            for job_id in to_reset:
                row = session.execute(
                    select(WorkResultStorage).where(WorkResultStorage.job_id == job_id)
                ).scalar_one_or_none()
                if row is not None:
                    session.delete(row)

    return len(to_reset)


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
        print(f"{db_path}: reset {count} spurious kill(s)")
        count2 = reset_uncovered_killed(db_path)
        print(f"{db_path}: reset {count2} uncovered-but-killed item(s)")
        total += count + count2

    if len(paths) > 1:
        print(f"Total: reset {total} item(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
