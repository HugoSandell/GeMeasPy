"""Compare mutation kills between the random and ACTS test generators.

Reads completed cosmic-ray session files from test_data/ and writes two JSON
files per suite size: one for mutations only killed by that random suite (vs all
ACTS kills), one for mutations only killed by that ACTS suite (vs all random
kills).
"""

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
_Fp = tuple[str, str, int]

def _load_kills(session_file: Path) -> tuple[set[_Fp], set[_Fp]] | None:
    """Return (killed, all_mutations), or None if the session has pending items."""
    killed:  set[_Fp] = set()
    all_mut: set[_Fp] = set()
    with work_db.use_db(str(session_file), mode=WorkDB.Mode.open) as db:  # type: ignore[attr-defined]
        if db.pending_work_items:
            return None
        for work_item, result in db.completed_work_items:
            for mutation in work_item.mutations:
                fp = (str(mutation.module_path), mutation.operator_name, mutation.occurrence)
                all_mut.add(fp)
                if result.test_outcome == TestOutcome.KILLED:
                    killed.add(fp)
    return killed, all_mut


def _suite_size(session_file: Path) -> tuple[str, int]:
    """Get the suite suffix and size from a session filename"""
    end_split = session_file.stem.rsplit("_", 2)
    final = end_split[-1]
    if final.startswith("s"):
        if len(end_split) != 3:
            raise ValueError(f"Unsupported file name {session_file.stem}. Expected ending in _<size> or _<size>_s<seed>.")
        return (f"{end_split[-2]}_{final}", int(end_split[-2]))
    return final, int(final)



def main() -> None:
    only_seed = sys.argv[1] if len(sys.argv) > 1 else None

    root_dir = Path(gemeaspy.__file__).parent.parent
    data_dir = root_dir / "test_data"

    if not data_dir.is_dir():
        print(f"test_data/ not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    random_files = sorted(data_dir.glob("cosmicray_random_*.sqlite"))
    acts_files   = sorted(data_dir.glob("cosmicray_acts_*.sqlite"))

    if only_seed is not None:
        random_files = [f for f in random_files if f.stem.endswith(f"_s{only_seed}")]

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
    random_kills: dict[int, dict[str, set[_Fp]]] = {}
    for f in random_files:
        suffix, size = _suite_size(f)
        result = _load_kills(f)
        if result is None:
            print(f"  {with_sgr(f.name, STYLE_DIM)}: skipped (pending items)")
            continue
        batch, _ = result
        if size not in random_kills:
            random_kills[size] = {}
        random_kills[size][suffix] = batch
        print(f"  {with_sgr(f.name, STYLE_DIM)}: {len(batch)} killed")

    acts_kills:  dict[int, set[_Fp]] = {}
    total_muts:  dict[int, set[_Fp]] = {}
    for f in acts_files:
        suffix, size = _suite_size(f)
        result = _load_kills(f)
        if result is None:
            print(f"  {with_sgr(f.name, STYLE_DIM)}: skipped (pending items)")
            continue
        batch, all_mut = result
        acts_kills[size]  = batch
        total_muts[size]  = all_mut
        print(f"  {with_sgr(f.name, STYLE_DIM)}: {len(batch)} killed")

    all_sizes = sorted(random_kills.keys() | acts_kills.keys())
    paired_sizes   = [s for s in all_sizes if s in random_kills and s in acts_kills]
    unpaired_random = [s for s in all_sizes if s in random_kills and s not in acts_kills]
    unpaired_acts   = [s for s in all_sizes if s in acts_kills   and s not in random_kills]

    if unpaired_random:
        print(f"Warning: no matching ACTS session for random size(s): {', '.join(', '.join(random_kills[k].keys()) for k in unpaired_random)}", file=sys.stderr)
    if unpaired_acts:
        print(f"Warning: no matching random session for ACTS size(s): {', '.join(str(s) for s in unpaired_acts)}", file=sys.stderr)

    print()
    for size in paired_sizes:
        a_killed = acts_kills[size]
        total    = total_muts[size]
        both_counts:    list[int] = []
        random_counts:  list[int] = []
        acts_counts:    list[int] = []
        survive_counts: list[int] = []

        for r_killed in random_kills[size].values():
            both_counts.append(len(r_killed & a_killed))
            random_counts.append(len(r_killed - a_killed))
            acts_counts.append(len(a_killed - r_killed))
            survive_counts.append(len(total - (r_killed | a_killed)))

        n = len(both_counts)
        avg_both    = sum(both_counts)    / n
        avg_random  = sum(random_counts)  / n
        avg_acts    = sum(acts_counts)    / n
        avg_survive = sum(survive_counts) / n

        print(with_sgr(f"Size {size} (avg over {n} seed{'s' if n != 1 else ''}):", STYLE_BOLD))
        print(f"  killed by both:    {with_sgr(f'{avg_both:.3f}', CLR_GREEN_FG)}")
        print(f"  killed by random:  {with_sgr(f'{avg_random:.3f}', CLR_YELLOW_FG)}")
        print(f"  killed by acts:    {with_sgr(f'{avg_acts:.3f}', CLR_YELLOW_FG)}")
        print(f"  survive both:      {with_sgr(f'{avg_survive:.3f}', CLR_YELLOW_FG)}")
        print()

if __name__ == "__main__":
    main()