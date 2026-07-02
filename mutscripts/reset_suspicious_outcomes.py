"""Reset work items killed by test failures known to be caused by problems with the execution environment."""
import glob
import json
import sys
from pathlib import Path

from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkResultStorage
from gemeaspy.tests.coverage_utils import is_covered as _is_covered

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


def reset_job(db_path: str, job_id: str) -> bool:
    from sqlalchemy import select

    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        with db._session_maker.begin() as session:  # type: ignore[attr-defined]
            row = session.execute(
                select(WorkResultStorage).where(WorkResultStorage.job_id == job_id)
            ).scalar_one_or_none()
            if row is None:
                return False
            session.delete(row)
    return True


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", metavar="DB", nargs="+", help="Path(s) to cosmic-ray session sqlite file(s); supports wildcards")
    parser.add_argument("--job", metavar="JOB_ID", help="Reset a specific job ID regardless of outcome")
    args = parser.parse_args(argv[1:])

    paths: list[str] = []
    for pattern in args.db:
        expanded = glob.glob(pattern)
        if not expanded:
            print(f"Error: {pattern!r} matches no files", file=sys.stderr)
            return 1
        paths.extend(sorted(expanded))

    if args.job:
        found = False
        for db_path in paths:
            if not Path(db_path).exists():
                print(f"Error: {db_path!r} does not exist", file=sys.stderr)
                return 1
            if reset_job(db_path, args.job):
                print(f"{Path(db_path).name}: reset job {args.job!r}")
                found = True
        if not found:
            print(f"Job {args.job!r} not found in any of the specified databases.", file=sys.stderr)
            return 1
        return 0

    total = 0
    for db_path in paths:
        if not Path(db_path).exists():
            print(f"Error: {db_path!r} does not exist", file=sys.stderr)
            return 1
        count = reset_spurious_kills(db_path)
        print(f"{Path(db_path).name}: reset {count} spurious kill(s)")
        count2 = reset_uncovered_killed(db_path)
        print(f"{Path(db_path).name}: reset {count2} uncovered-but-killed item(s)")
        total += count + count2

    if len(paths) > 1:
        print(f"Total: reset {total} item(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
