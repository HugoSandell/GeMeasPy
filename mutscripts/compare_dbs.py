"""Compare two cosmic-ray database files.

Verifies that all mutations and their diffs are identical between the two
databases, then reports any entries where the test outcome differs.
"""
import typing
import sys
from pathlib import Path

from cosmic_ray import work_db
from cosmic_ray.work_db import WorkDB



def _load(db_path: str) -> dict[tuple, tuple]:
    """Return {(module_path, operator, occurrence): (job_id, outcome, diff)} for all completed items."""
    rows: dict[tuple, tuple] = {}
    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        for wi, result in db.completed_work_items:
            for m in wi.mutations:
                key = (str(m.module_path), m.operator_name, m.occurrence)
                rows[key] = (wi.job_id, result.test_outcome, result.diff or "")
        for wi in db.pending_work_items:
            for m in wi.mutations:
                key = (str(m.module_path), m.operator_name, m.occurrence)
                rows[key] = (wi.job_id, "PENDING", "")
    return rows


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"Usage: python {argv[0]} <db_a> <db_b>", file=sys.stderr)
        return 1

    path_a, path_b = argv[1], argv[2]
    for p in (path_a, path_b):
        if not Path(p).exists():
            print(f"Error: {p!r} does not exist", file=sys.stderr)
            return 1

    print(f"Loading {Path(path_a).name} ...")
    rows_a = _load(path_a)
    print(f"Loading {Path(path_b).name} ...")
    rows_b = _load(path_b)

    keys_a = set(rows_a)
    keys_b = set(rows_b)
    only_a = keys_a - keys_b
    only_b = keys_b - keys_a

    ok = True

    if only_a:
        print(f"\nOnly in {Path(path_a).name} ({len(only_a)}):")
        for k in sorted(only_a):
            print(f"  {k[0]}  {k[1]} #{k[2]}")
        ok = False

    if only_b:
        print(f"\nOnly in {Path(path_b).name} ({len(only_b)}):")
        for k in sorted(only_b):
            print(f"  {k[0]}  {k[1]} #{k[2]}")
        ok = False

    common = keys_a & keys_b

    diff_mismatches: list[tuple] = []
    outcome_diffs: list[tuple] = []

    for k in common:
        _, out_a, diff_a = rows_a[k]
        _, out_b, diff_b = rows_b[k]
        if diff_a != diff_b:
            diff_mismatches.append((k, diff_a, diff_b))
        if out_a != out_b:
            outcome_diffs.append((k, out_a, out_b))

    # Ignore diff mismatches where one side is pending (no diff yet)
    real_diff_mismatches = [
        (k, da, db) for k, da, db in diff_mismatches
        if rows_a[k][1] != "PENDING" and rows_b[k][1] != "PENDING"
    ]

    if real_diff_mismatches:
        print(f"\nDiff mismatches ({len(real_diff_mismatches)}):")
        for k, diff_a, diff_b in real_diff_mismatches:
            print(f"  {k[0]}  {k[1]} #{k[2]}")
            if diff_a:
                print(f"    A: {diff_a.splitlines()[0]!r} ...")
            if diff_b:
                print(f"    B: {diff_b.splitlines()[0]!r} ...")
        ok = False
    else:
        pending_skipped = len(diff_mismatches) - len(real_diff_mismatches)
        note = f" ({pending_skipped} skipped - one side pending)" if pending_skipped else ""
        print(f"\nDiffs: all completed shared mutations have identical diffs{note}.")

    label_a = f"A: {Path(path_a).name}"
    label_b = f"B: {Path(path_b).name}"
    col = max(len(label_a), len(label_b))

    if outcome_diffs:
        print(f"\nOutcome differences ({len(outcome_diffs)}):")
        for k, out_a, out_b in sorted(outcome_diffs, key=lambda x: x[0]):
            module, operator, occ = k
            print(f"  {module}  {operator} #{occ}")
            print(f"    {label_a:<{col}}  {out_a}")
            print(f"    {label_b:<{col}}  {out_b}")
    else:
        print(f"Outcomes: all {len(common)} shared mutations have identical outcomes.")

    return 0 if ok and not outcome_diffs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
