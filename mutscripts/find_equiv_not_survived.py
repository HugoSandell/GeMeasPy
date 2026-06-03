"""Find equivalent mutants (from equivalent_mutants.json) that are present in a cosmic-ray session DB but whose outcome is not SURVIVED.
"""
import argparse
import glob
import json
import sys
from pathlib import Path

from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkResultStorage

EQUIV_FILE = Path("test_data/equivalent_mutants.json")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("db", metavar="DB", nargs="+", help="Path(s) to cosmic-ray session sqlite file(s); supports wildcards")
parser.add_argument(
    "--reset-incompetent",
    action="store_true",
    help="Delete INCOMPETENT result rows for equivalent mutants so they will be re-run",
)
parser.add_argument(
    "--reset-killed",
    action="store_true",
    help="Delete KILLED result rows for equivalent mutants so they will be re-run",
)
parser.add_argument(
    "--reset",
    action="store_true",
    help="Delete KILLED and INCOMPETENT result rows for equivalent mutants so they will be re-run",
)
args = parser.parse_args()

db_paths: list[str] = []
for pattern in args.db:
    expanded = glob.glob(pattern)
    if not expanded:
        print(f"Error: {pattern!r} matches no files", file=sys.stderr)
        sys.exit(1)
    db_paths.extend(sorted(expanded))

with open(EQUIV_FILE, encoding="utf-8") as f:
    entries = json.load(f)

equiv: dict[tuple, str] = {
    (e["module_path"].replace("\\", "/"), e["operator_name"], e["occurrence"]): e["reason"]
    for e in entries
}

total_killed: list[tuple] = []
total_skipped: list[tuple] = []
total_incompetent_reset = 0
total_killed_reset = 0

for db_path in db_paths:
    if not Path(db_path).exists():
        print(f"Error: {db_path!r} does not exist", file=sys.stderr)
        sys.exit(1)

    if len(db_paths) > 1:
        print(f"\n=== {Path(db_path).name} ===")

    killed: list[tuple] = []
    skipped: list[tuple] = []
    incompetent_job_ids: list[str] = []

    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        for work_item, result in db.completed_work_items:
            for mutation in work_item.mutations:
                mutation_data = (
                    str(mutation.module_path).replace("\\", "/"),
                    mutation.operator_name,
                    mutation.occurrence,
                    mutation.start_pos,
                    work_item.job_id,
                    result.test_outcome
                )
                if mutation_data[:3] not in equiv:
                    continue
                if result.test_outcome == TestOutcome.SURVIVED:
                    continue
                if result.test_outcome == TestOutcome.KILLED:
                    killed.append(mutation_data)
                else:
                    skipped.append(mutation_data)
                    if result.test_outcome == TestOutcome.INCOMPETENT:
                        incompetent_job_ids.append(work_item.job_id)

    print(f"Equivalent mutants in json : {len(equiv)}")
    print(f"Killed (false equivalents) : {len(killed)}")
    print(f"Skipped (not covered)      : {len(skipped)}")

    if killed:
        print("\n--- KILLED (false equivalents) ---")
        for mutation_data in killed:
            m, op, occ, start_pos, job_id, test_outcome = mutation_data
            print(f"  {m}:{start_pos[0]} | {op} #{occ}")
            print(f"    equivalence reason: {equiv[mutation_data[:3]]}")
            print(f"    job: {job_id}")
            print(f"    test outcome: {test_outcome}")

    if skipped:
        print("\n--- SKIPPED (not covered) ---")
        for mutation_data in skipped:
            m, op, occ, start_pos, job_id, test_outcome = mutation_data
            print(f"  {m}:{start_pos[0]} | {op} #{occ}")
            print(f"    equivalence reason: {equiv[mutation_data[:3]]}")
            print(f"    job: {job_id}")
            print(f"    test outcome: {test_outcome}")
            
    if args.reset_killed or args.reset:
        killed_job_ids = [k[4] for k in killed]
        if not killed_job_ids:
            print("\nNo KILLED equivalent mutants to reset.")
        else:
            from sqlalchemy import select
            with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
                with db._session_maker.begin() as session:  # type: ignore[attr-defined]
                    rows = (
                        session.execute(
                            select(WorkResultStorage).where(
                                WorkResultStorage.job_id.in_(killed_job_ids)
                            )
                        )
                        .scalars()
                        .all()
                    )
                    for row in rows:
                        session.delete(row)
            reset_count = len(rows)
            total_killed_reset += reset_count
            print(f"\nReset {total_killed_reset} KILLED equivalent mutant(s).")
    if args.reset_incompetent or args.reset:
        if not incompetent_job_ids:
            print("\nNo INCOMPETENT equivalent mutants to reset.")
        else:
            from sqlalchemy import select
            with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
                with db._session_maker.begin() as session:  # type: ignore[attr-defined]
                    rows = (
                        session.execute(
                            select(WorkResultStorage).where(
                                WorkResultStorage.job_id.in_(incompetent_job_ids)
                            )
                        )
                        .scalars()
                        .all()
                    )
                    for row in rows:
                        session.delete(row)
            reset_count = len(rows)
            total_incompetent_reset += reset_count
            print(f"\nReset {reset_count} INCOMPETENT equivalent mutant(s).")

    total_killed.extend(killed)
    total_skipped.extend(skipped)

if len(db_paths) > 1:
    print(f"\n=== TOTAL across {len(db_paths)} databases ===")
    print(f"Killed (false equivalents) : {len(total_killed)}")
    print(f"Skipped (not covered)      : {len(total_skipped)}")
    if args.reset_incompetent:
        print(f"Reset INCOMPETENT          : {total_incompetent_reset}")
