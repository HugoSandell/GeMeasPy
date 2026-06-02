"""Export mutation scores for a given suite type and size to CSV.

Usage:
    python results_to_csv.py random <size>
    python results_to_csv.py acts <size>

Reads cosmicray_<type>_<size>[_s<seed>].sqlite from test_data/ and writes as CSV
"""

import csv
import json
import sys
from pathlib import Path

from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB
from gemeaspy.tests.coverage_utils import is_covered as _is_covered


def _load_equivalent_fps(data_dir: Path) -> set[tuple[str, str, int]]:
    path = data_dir / "equivalent_mutants.json"
    if not path.is_file():
        return set()
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return {(e["module_path"], e["operator_name"], e["occurrence"]) for e in entries}


def _load_covered_lines(coverage_json: Path) -> dict[str, set[int]]:
    if not coverage_json.is_file():
        return {}
    with open(coverage_json, encoding="utf-8") as f:
        cov_data = json.load(f)
    covered: dict[str, set[int]] = {}
    for filepath, file_data in cov_data.get("files", {}).items():
        covered[str(Path(filepath).resolve())] = set(file_data.get("executed_lines", []))
    return covered




def score_db(
    db_path: Path,
    coverage_json: Path,
    equivalent_fps: set[tuple[str, str, int]],
    root: Path,
) -> dict[str, int] | None:
    covered = _load_covered_lines(coverage_json)
    killed = survived = incompetent = equivalent = uncovered = 0

    with work_db.use_db(str(db_path), mode=WorkDB.Mode.open) as db:  # type: ignore[attr-defined]
        if db.pending_work_items:
            return None
        for work_item, result in db.completed_work_items:
            outcome = result.test_outcome
            if outcome == TestOutcome.KILLED:
                killed += 1
            elif outcome == TestOutcome.SURVIVED:
                survived += 1
            elif outcome == TestOutcome.INCOMPETENT:
                incompetent += 1
            if outcome == TestOutcome.SURVIVED:
                for mutation in work_item.mutations:
                    fp = (str(mutation.module_path), mutation.operator_name, mutation.occurrence)
                    if fp in equivalent_fps:
                        equivalent += 1
                    elif covered and not _is_covered(
                        str(mutation.module_path), mutation.start_pos[0], covered, root
                    ):
                        uncovered += 1

    return dict(killed=killed, survived=survived, equivalent=equivalent,
                uncovered=uncovered, incompetent=incompetent)


def main() -> None:
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} {{random|acts}} <size> [output.csv]",
              file=sys.stderr)
        sys.exit(1)

    suite_type = sys.argv[1]
    if suite_type not in ("random", "acts"):
        print(f"Suite type must be 'random' or 'acts', got {suite_type!r}", file=sys.stderr)
        sys.exit(1)

    size = int(sys.argv[2])
    data_dir = Path(__file__).resolve().parent.parent / "test_data"
    root = data_dir.parent

    if not data_dir.is_dir():
        print(f"test_data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    equivalent_fps = _load_equivalent_fps(data_dir)

    if suite_type == "random":
        sessions: list[tuple[int | None, Path]] = []
        for path in data_dir.glob(f"cosmicray_random_{size}_s*.sqlite"):
            tail = path.stem.split("_")[-1]
            if tail.startswith("s"):
                try:
                    sessions.append((int(tail[1:]), path))
                except ValueError:
                    pass
        sessions.sort(key=lambda x: x[0])  # type: ignore[arg-type]
    else:
        db_path = data_dir / f"cosmicray_acts_{size}.sqlite"
        sessions = [(None, db_path)] if db_path.is_file() else []

    if not sessions:
        print(f"No {suite_type} sessions found for size {size} in {data_dir}", file=sys.stderr)
        sys.exit(1)

    writer = csv.writer(sys.stdout)
    writer.writerow(["Seed", "Killed", "Survived", "Equivalent", "Uncovered", "Incompetent"])
    for seed, db_path in sessions:
        label = f"random_{size}_s{seed}" if suite_type == "random" else f"acts_{size}"
        coverage_json = data_dir / f"baseline_{label}_coverage.json"
        scores = score_db(db_path, coverage_json, equivalent_fps, root)
        if scores is None:
            continue
        writer.writerow([
            seed if seed is not None else "",
            scores["killed"],
            scores["survived"],
            scores["equivalent"],
            scores["uncovered"],
            scores["incompetent"],
        ])


if __name__ == '__main__':
    main()
