"""Find equivalent mutants (from equivalent_mutants.json) that are present in a cosmic-ray session DB but whose outcome is not SURVIVED.
"""
import argparse
import json
from pathlib import Path

from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB

EQUIV_FILE = Path("test_data/equivalent_mutants.json")

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("db", metavar="DB", help="Path to cosmic-ray session sqlite file")
args = parser.parse_args()

with open(EQUIV_FILE, encoding="utf-8") as f:
    entries = json.load(f)

equiv: dict[tuple, str] = {
    (e["module_path"].replace("\\", "/"), e["operator_name"], e["occurrence"]): e["reason"]
    for e in entries
}

killed: list[tuple] = []
skipped: list[tuple] = []

with work_db.use_db(args.db, mode=WorkDB.Mode.open) as db:
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
