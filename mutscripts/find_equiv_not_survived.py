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
            fp = (
                str(mutation.module_path).replace("\\", "/"),
                mutation.operator_name,
                mutation.occurrence,
            )
            if fp not in equiv:
                continue
            if result.test_outcome == TestOutcome.SURVIVED:
                continue
            if result.test_outcome == TestOutcome.KILLED:
                killed.append(fp)
            else:
                skipped.append(fp)

print(f"Equivalent mutants in json : {len(equiv)}")
print(f"Killed (false equivalents) : {len(killed)}")
print(f"Skipped (not covered)      : {len(skipped)}")

if killed:
    print("\n--- KILLED (false equivalents) ---")
    for fp in killed:
        m, op, occ = fp
        print(f"  {m} | {op} #{occ}")
        print(f"    reason: {equiv[fp]}")

if skipped:
    print("\n--- SKIPPED (not covered) ---")
    for fp in skipped:
        m, op, occ = fp
        print(f"  {m} | {op} #{occ}")
        print(f"    reason: {equiv[fp]}")
