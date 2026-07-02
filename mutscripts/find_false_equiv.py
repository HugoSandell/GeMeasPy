"""Find mutants marked equivalent in equivalent_mutants.json that were actually killed by some DB.
Optionally resets those items to pending to be re-tested (--reset flag).
"""
import argparse
import json
from pathlib import Path
from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkResultStorage

equiv_file = Path('test_data/equivalent_mutants.json')
with open(equiv_file, encoding='utf-8') as f:
    entries = json.load(f)

equiv = {(e['module_path'].replace('\\', '/'), e['operator_name'], e['occurrence']): e['reason'] for e in entries}

parser = argparse.ArgumentParser(description='Find false-equivalent mutants across cosmic-ray databases.')
parser.add_argument('tags', nargs='*', metavar='TAG',
                    help='Database tags to filter (e.g. 59_s3 matches test_data/*59_s3.sqlite)')
parser.add_argument('--reset', action='store_true',
                    help='Reset false-equivalent work items so cosmic-ray re-runs them')
args = parser.parse_args()

if args.tags:
    db_files = sorted(p for tag in args.tags for p in Path('test_data').glob(f'*{tag}.sqlite'))
else:
    db_files = sorted(Path('test_data').glob('*.sqlite'))

# fingerprint -> {'dbs': set of db names, 'diff': first diff seen}
hits: dict[tuple, dict] = {}
for db_path in db_files:
    with work_db.use_db(str(db_path), mode=WorkDB.Mode.open) as db:
        for work_item, result in db.completed_work_items:
            if result.test_outcome != TestOutcome.KILLED:
                continue
            for mutation in work_item.mutations:
                fp = (str(mutation.module_path).replace('\\', '/'), mutation.operator_name, mutation.occurrence)
                if fp not in equiv:
                    continue
                entry = hits.setdefault(fp, {'dbs': set(), 'diff': None})
                entry['dbs'].add(db_path.name)
                if entry['diff'] is None and result.diff:
                    entry['diff'] = result.diff.strip()

def _reset_false_equivalents(db_path: str, false_equiv_fps: set) -> int:
    from sqlalchemy import select

    with work_db.use_db(db_path, mode=WorkDB.Mode.open) as db:
        seen: set = set()
        job_ids = []
        for work_item, result in db.completed_work_items:
            if result.test_outcome != TestOutcome.KILLED or work_item.job_id in seen:
                continue
            for mutation in work_item.mutations:
                fp = (str(mutation.module_path).replace('\\', '/'), mutation.operator_name, mutation.occurrence)
                if fp in false_equiv_fps:
                    job_ids.append(work_item.job_id)
                    seen.add(work_item.job_id)
                    break

        with db._session_maker.begin() as session:  # type: ignore[attr-defined]
            rows = (
                session.execute(
                    select(WorkResultStorage).where(WorkResultStorage.job_id.in_(job_ids))
                )
                .scalars()
                .all()
            )
            count = len(rows)
            for row in rows:
                session.delete(row)
    return count


print(f"Databases scanned: {len(db_files)}")
print(f"Equivalent mutants: {len(equiv)}")
print(f"Killed by at least one DB: {len(hits)}")
print()
for (m, op, occ), reason in sorted(equiv.items()):
    if (m, op, occ) not in hits:
        continue
    entry = hits[(m, op, occ)]
    dbs = sorted(entry['dbs'])
    print(f"=== {m} | {op} #{occ} ===")
    print(f"  reason: {reason}")
    print(f"  killed by: {', '.join(dbs)}")
    if entry['diff']:
        print(entry['diff'])
    print()

if args.reset and hits:
    false_equiv_fps = set(hits.keys())
    total = 0
    for db_path in db_files:
        count = _reset_false_equivalents(str(db_path), false_equiv_fps)
        print(f"{db_path.name}: reset {count} item(s)")
        total += count

    if len(db_files) > 1:
        print(f"Total: reset {total} item(s)")
