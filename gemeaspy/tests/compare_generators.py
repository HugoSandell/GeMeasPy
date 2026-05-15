"""Compare mutation kills between the random and ACTS test generators.

Reads completed cosmic-ray session files from test_data/ and writes two JSON
files per suite size: one for mutations only killed by that random suite (vs all
ACTS kills), one for mutations only killed by that ACTS suite (vs all random
kills).
"""

import json
import sys
from pathlib import Path

import gemeaspy
from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB
from gemeaspy.tests._sgr import (
    CLR_GREEN_FG, CLR_YELLOW_FG, 
    STYLE_BOLD, STYLE_DIM,
    with_sgr,
)
def _load_kills(session_file: Path) -> set[tuple[str, str, int]]:
    """Return fingerprints of KILLED mutations from a cosmic-ray session file"""
    killed: set[tuple[str, str, int]] = set()
    with work_db.use_db(str(session_file), mode=WorkDB.Mode.open) as db:  # type: ignore[attr-defined]
        for work_item, result in db.completed_work_items:
            if result.test_outcome == TestOutcome.KILLED:
                for mutation in work_item.mutations:
                    killed.add((str(mutation.module_path), mutation.operator_name, mutation.occurrence))
    return killed


def _suite_size(session_file: Path) -> str:
    """Get the suite size suffix from a session filename"""
    return session_file.stem.rsplit("_", 1)[-1]


def _write_json(path: Path, fingerprints: set[tuple[str, str, int]]) -> None:
    entries = sorted(
        [{"module_path": m, "operator_name": op, "occurrence": occ} for m, op, occ in fingerprints],
        key=lambda e: (e["module_path"], e["operator_name"], e["occurrence"]),
    )
    with path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")


def main() -> None:
    root_dir = Path(gemeaspy.__file__).parent.parent
    data_dir = root_dir / "test_data"

    if not data_dir.is_dir():
        print(f"test_data/ not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    random_files = sorted(data_dir.glob("cosmicray_random_*.sqlite"))
    acts_files   = sorted(data_dir.glob("cosmicray_acts_*.sqlite"))

    missing = []
    if not random_files:
        missing.append("random")
    if not acts_files:
        missing.append("acts")
    if missing:
        print(f"No session files found for: {', '.join(missing)}", file=sys.stderr)
        print("Run 'python -m gemeaspy.tests.mutate' first", file=sys.stderr)
        sys.exit(1)

    # Load kills per file, keyed by suite size
    random_kills: dict[str, set[tuple[str, str, int]]] = {}
    for f in random_files:
        size = _suite_size(f)
        batch = _load_kills(f)
        random_kills[size] = batch
        print(f"  {with_sgr(f.name, STYLE_DIM)}: {len(batch)} killed")

    acts_kills: dict[str, set[tuple[str, str, int]]] = {}
    for f in acts_files:
        size = _suite_size(f)
        batch = _load_kills(f)
        acts_kills[size] = batch
        print(f"  {with_sgr(f.name, STYLE_DIM)}: {len(batch)} killed")

    all_sizes = sorted(random_kills.keys() | acts_kills.keys())
    paired_sizes   = [s for s in all_sizes if s in random_kills and s in acts_kills]
    unpaired_random = [s for s in all_sizes if s in random_kills and s not in acts_kills]
    unpaired_acts   = [s for s in all_sizes if s in acts_kills   and s not in random_kills]

    if unpaired_random:
        print(f"Warning: no matching ACTS session for random size(s): {', '.join(unpaired_random)}", file=sys.stderr)
    if unpaired_acts:
        print(f"Warning: no matching random session for ACTS size(s): {', '.join(unpaired_acts)}", file=sys.stderr)

    print()
    for size in paired_sizes:
        r_killed = random_kills[size]
        a_killed = acts_kills[size]
        only_random = r_killed - a_killed
        only_acts   = a_killed - r_killed
        both        = r_killed & a_killed

        print(with_sgr(f"Size {size}:", STYLE_BOLD))
        print(f"  random killed:     {len(r_killed)}")
        print(f"  acts killed:       {len(a_killed)}")
        print(f"  killed by both:    {with_sgr(str(len(both)), CLR_GREEN_FG)}")
        print(f"  only by random:    {with_sgr(str(len(only_random)), CLR_YELLOW_FG if only_random else CLR_GREEN_FG)}")
        print(f"  only by acts:      {with_sgr(str(len(only_acts)),   CLR_YELLOW_FG if only_acts   else CLR_GREEN_FG)}")

        only_random_file = data_dir / f"only_random_{size}_killed.json"
        only_acts_file   = data_dir / f"only_acts_{size}_killed.json"
        _write_json(only_random_file, only_random)
        _write_json(only_acts_file,   only_acts)
        print(f"  → {with_sgr(str(only_random_file), STYLE_DIM)}")
        print(f"  → {with_sgr(str(only_acts_file),   STYLE_DIM)}")
        print()

if __name__ == "__main__":
    main()