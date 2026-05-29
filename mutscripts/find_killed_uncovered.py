"""Lists mutants that are marked as killed despite being uncovered.

Usage: python -m mutscripts.find_killed_uncovered [options] <label>
"""

import argparse
from collections.abc import Iterable
from pathlib import Path

from cosmic_ray import work_db
from cosmic_ray.work_db import WorkDB
from cosmic_ray.work_item import MutationSpec, TestOutcome, WorkerOutcome

from gemeaspy.tests._sgr import CLR_GREEN_FG, CLR_RED_FG, with_sgr

from .mutation_score_statistics import _is_covered, load_coverage_lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", nargs="+", help="session label, e.g. random_59_s0")
    parser.add_argument(
        "--data-dir",
        default="test_data",
        help="directory with cosmicray_*.sqlite and baseline_* files (default: test_data)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    root = Path(__file__).parent.parent

    for label in args.label:
        print(f"{label}:")
        covered = load_coverage_lines(data_dir / f"baseline_{label}_coverage.json")
        expected_uncovered = 0
        found = False

        def uncovered_mutations(
            mutations: Iterable[MutationSpec],
        ) -> Iterable[MutationSpec]:
            return filter(
                lambda mutation: (
                    covered
                    and not _is_covered(
                        str(mutation.module_path), mutation.start_pos[0], covered, root
                    )
                ),
                mutations,
            )

        with work_db.use_db(
            str(data_dir / f"cosmicray_{label}.sqlite"), mode=WorkDB.Mode.open
        ) as db:
            for work_item, result in db.completed_work_items:
                if result.worker_outcome == WorkerOutcome.SKIPPED:
                    continue
                for mutation in uncovered_mutations(work_item.mutations):
                    expected_uncovered += 1

                    if result.test_outcome != TestOutcome.KILLED:
                        continue

                    found = True
                    fp_str = f"{mutation.module_path}:{mutation.start_pos[0]} {mutation.operator_name} #{mutation.occurrence}"
                    print(
                        with_sgr(
                            f"  {fp_str} (job_id='{work_item.job_id}')",
                            CLR_RED_FG,
                        )
                    )
            for work_item in db.pending_work_items:
                for mutation in uncovered_mutations(work_item.mutations):
                    expected_uncovered += 0

        print(f"  Expected uncovered mutants: {expected_uncovered}")
        if not found:
            print(with_sgr("  No killed uncovered mutants found", CLR_GREEN_FG))


if __name__ == "__main__":
    main()
