"""H1/H2/H3 statistical comparison of random vs. ACTS mutation test suites.

Scores each session (covered/full mutation score, branch coverage), then
runs Wilcoxon signed-rank, Wilson CI, Vargha-Delaney A12, and exact McNemar
tests for each suite size that has both an ACTS and random session.

Usage: python mutation_score_statistics.py [data_dir] [options]
"""

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from coverage import Coverage
from scipy import stats
from statsmodels.stats.proportion import proportion_confint

from cosmic_ray import work_db
from cosmic_ray.work_db import TestOutcome, WorkDB, WorkerOutcome

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gemeaspy.tests._sgr import (
    with_sgr,
    CLR_YELLOW_FG, CLR_CYAN_FG, CLR_BRIGHT_WHITE_FG,
    STYLE_BOLD,
)



_Fp = tuple[str, str, int]


@dataclass
class SuiteScore:
    """Scored outcome of a single test suite, mirroring mutate.print_summary."""
    label: str
    size: int
    seed: int | None
    killed: int
    survived: int
    incompetent: int
    no_test: int
    abnormal: int
    skipped: int
    equivalent: int
    uncovered: int
    pending: bool
    killed_fps: set[_Fp] = field(default_factory=set)
    universe_fps: set[_Fp] = field(default_factory=set)

    @property
    def covered_denom(self) -> int:
        return self.killed + self.survived - self.equivalent - self.uncovered

    @property
    def full_denom(self) -> int:
        return self.killed + self.survived - self.equivalent

    @property
    def covered_score(self) -> float:
        d = self.covered_denom
        return self.killed / d if d > 0 else float('nan')

    @property
    def full_score(self) -> float:
        d = self.full_denom
        return self.killed / d if d > 0 else float('nan')


def load_equivalent_fingerprints(data_dir: Path) -> set[_Fp]:
    """Load manually tagged equivalent mutants from equivalent_mutants.json."""
    path = data_dir / "equivalent_mutants.json"
    if not path.is_file():
        return set()
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return {(e["module_path"], e["operator_name"], e["occurrence"]) for e in entries}


def load_coverage_lines(coverage_json: Path) -> dict[str, set[int]]:
    """Return {resolved_absolute_path: {executed_line_numbers}} from a coverage JSON."""
    if not coverage_json.is_file():
        return {}
    with open(coverage_json, encoding="utf-8") as f:
        cov_data = json.load(f)
    covered: dict[str, set[int]] = {}
    for filepath, file_data in cov_data.get("files", {}).items():
        covered[str(Path(filepath).resolve())] = set(file_data.get("executed_lines", []))
    return covered


def _is_covered(module_path: str, line: int, covered: dict[str, set[int]], root: Path) -> bool:
    module_abs = str((root / module_path).resolve())
    return module_abs in covered and line in covered[module_abs]


def score_session(
    session_path: Path,
    coverage_json: Path,
    equivalent_fps: set[_Fp],
    root: Path,
    label: str,
    size: int,
    seed: int | None,
) -> SuiteScore | None:
    """Score one Cosmic Ray session. Returns None if the database cannot be opened."""
    covered = load_coverage_lines(coverage_json)

    killed = survived = incompetent = no_test = abnormal = skipped = 0
    equivalent = uncovered = 0
    killed_fps: set[_Fp] = set()
    universe_fps: set[_Fp] = set()
    pending = False

    with work_db.use_db(str(session_path), mode=WorkDB.Mode.open) as db:  # type: ignore[attr-defined]
        if db.pending_work_items:
            pending = True
        for work_item, result in db.completed_work_items:
            outcome = result.test_outcome
            worker = result.worker_outcome
            if outcome == TestOutcome.KILLED:
                killed += 1
            elif outcome == TestOutcome.SURVIVED:
                survived += 1
            elif outcome == TestOutcome.INCOMPETENT:
                incompetent += 1
            if worker == WorkerOutcome.NO_TEST:
                no_test += 1
            elif worker == WorkerOutcome.ABNORMAL:
                abnormal += 1
            elif worker == WorkerOutcome.SKIPPED:
                skipped += 1

            for mutation in work_item.mutations:
                fp = (str(mutation.module_path), mutation.operator_name, mutation.occurrence)
                universe_fps.add(fp)
                if outcome == TestOutcome.KILLED:
                    killed_fps.add(fp)
                if outcome == TestOutcome.SURVIVED:
                    if fp in equivalent_fps:
                        equivalent += 1
                    elif covered and not _is_covered(
                        str(mutation.module_path), mutation.start_pos[0], covered, root
                    ):
                        uncovered += 1

    return SuiteScore(
        label=label, size=size, seed=seed,
        killed=killed, survived=survived, incompetent=incompetent,
        no_test=no_test, abnormal=abnormal, skipped=skipped,
        equivalent=equivalent, uncovered=uncovered, pending=pending,
        killed_fps=killed_fps, universe_fps=universe_fps,
    )


# Branch coverage from .coverage files
def branch_coverage(coverage_data_file: Path) -> float | None:
    """Branch-coverage fraction from a coverage.py data file, or None if unavailable."""
    if not coverage_data_file.is_file():
        return None
    coveragerc = coverage_data_file.with_suffix('.coveragerc')
    cfg = str(coveragerc) if coveragerc.exists() else False
    cov = Coverage(data_file=str(coverage_data_file), config_file=cfg, branch=True)
    cov.load()
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as tmp:
        tmp_path = tmp.name
    try:
        cov.json_report(outfile=tmp_path, ignore_errors=True)
        with open(tmp_path) as f:
            totals = json.load(f).get('totals', {})
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    num_b = totals.get('num_branches', 0)
    cov_b = totals.get('covered_branches', 0)
    return cov_b / num_b if num_b > 0 else None


# Suite discovery
@dataclass
class SizeGroup:
    size: int
    acts_session: Path | None = None
    random_sessions: dict[int, Path] = field(default_factory=dict)  # seed -> path


def _parse_random_stem(stem: str) -> tuple[int, int] | None:
    # cosmicray_random_59_s7 -> (59, 7)
    parts = stem.split('_')
    if len(parts) < 4 or parts[0] != 'cosmicray' or parts[1] != 'random':
        return None
    if not parts[-1].startswith('s'):
        return None
    try:
        return int(parts[-2]), int(parts[-1][1:])
    except ValueError:
        return None


def _parse_acts_stem(stem: str) -> int | None:
    # cosmicray_acts_456 -> 456
    parts = stem.split('_')
    if len(parts) != 3 or parts[0] != 'cosmicray' or parts[1] != 'acts':
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def discover_groups(data_dir: Path) -> dict[int, SizeGroup]:
    groups: dict[int, SizeGroup] = {}
    for path in sorted(data_dir.glob("cosmicray_acts_*.sqlite")):
        size = _parse_acts_stem(path.stem)
        if size is None:
            continue
        groups.setdefault(size, SizeGroup(size)).acts_session = path
    for path in sorted(data_dir.glob("cosmicray_random_*.sqlite")):
        parsed = _parse_random_stem(path.stem)
        if parsed is None:
            continue
        size, seed = parsed
        groups.setdefault(size, SizeGroup(size)).random_sessions[seed] = path
    return groups


# Statistics                                                                  #

@dataclass
class MetricComparison:
    metric: str
    size: int
    n: int
    mean: float
    sd: float
    median: float
    minimum: float
    maximum: float
    acts: float | None
    diff_pp: float | None
    wilcoxon_p: float | None
    prop_ge: float | None
    prop_ci: tuple[float, float] | None
    a12: float | None
    prop_count: int | None = None


def summary(values: np.ndarray) -> tuple[int, float, float, float, float, float]:
    v = values[~np.isnan(values)]
    n = len(v)
    if n == 0:
        nan = float('nan')
        return 0, nan, nan, nan, nan, nan
    sd = float(v.std(ddof=1)) if n > 1 else float('nan')
    return n, float(v.mean()), sd, float(np.median(v)), float(v.min()), float(v.max())


def vargha_delaney_a12(acts_value: float, random_scores: np.ndarray) -> float:
    """Vargha-Delaney A12: P(ACTS > random) + 0.5*P(ACTS = random)."""
    x = random_scores[~np.isnan(random_scores)]
    n = len(x)
    if n == 0:
        return float('nan')
    greater = float(np.sum(acts_value > x))
    ties = float(np.sum(acts_value == x))
    return (greater + 0.5 * ties) / n


def wilcoxon_vs_constant(random_scores: np.ndarray, acts_value: float) -> float:
    """One-sided Wilcoxon signed-rank p-value testing H: ACTS > random distribution."""
    x = random_scores[~np.isnan(random_scores)]
    d = x - acts_value
    if len(d) == 0 or np.all(d == 0):
        return float('nan')
    return float(stats.wilcoxon(d, alternative='less').pvalue) # type: ignore


def proportion_ge(random_scores: np.ndarray, acts_value: float, alpha: float
                  ) -> tuple[int, int, float, float, float]:
    """Count and proportion of random suites with score >= ACTS, with a Wilson CI."""
    x = random_scores[~np.isnan(random_scores)]
    n = len(x)
    k = int(np.sum(x >= acts_value)) 
    if n == 0:
        return 0, 0, float('nan'), float('nan'), float('nan')
    lo, hi = proportion_confint(k, n, alpha=alpha, method='wilson')
    return k, n, k / n, float(lo), float(hi)  # type: ignore


def compare_metric(metric: str, size: int, random_scores: np.ndarray,
                   acts_value: float | None, alpha: float) -> MetricComparison:
    n, mean, sd, median, mn, mx = summary(random_scores)
    if acts_value is None or np.isnan(acts_value):
        return MetricComparison(metric, size, n, mean, sd, median, mn, mx,
                                None, None, None, None, None, None)
    diff_pp = (acts_value - mean) * 100.0
    wp = wilcoxon_vs_constant(random_scores, acts_value)
    k, nn, p_ge, lo, hi = proportion_ge(random_scores, acts_value, alpha)
    a12 = vargha_delaney_a12(acts_value, random_scores)
    return MetricComparison(metric, size, n, mean, sd, median, mn, mx,
                            acts_value, diff_pp, wp, p_ge, (lo, hi), a12, k)


def mcnemar_exact(b: int, c: int) -> float | None:
    """Exact (binomial, p=0.5) McNemar p-value for discordant counts b and c."""
    if b + c == 0:
        return None
    return float(stats.binomtest(b, b + c, 0.5, alternative='two-sided').pvalue)


# Reporting

def _fmt(x: float | None, places: int = 4) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    return f"{x:.{places}f}"


def _fmt_p(p: float | None) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "n/a"
    return f"{p:.2e}" if p < 1e-3 else f"{p:.4f}"


def print_size_header(size: int, label: str | None) -> None:
    tag = f" [{label}]" if label else ""
    print(f"\n{with_sgr(f'SUITE SIZE {size}{tag}', [STYLE_BOLD, CLR_BRIGHT_WHITE_FG])}")

def print_comparison(c: MetricComparison) -> None:
    print(f"\n  {with_sgr(c.metric, [STYLE_BOLD, CLR_CYAN_FG])}")
    print(f"    random (n={c.n}): mean={_fmt(c.mean)} SD={_fmt(c.sd)} "
          f"median={_fmt(c.median)} min={_fmt(c.minimum)} max={_fmt(c.maximum)}")
    if c.acts is None:
        print(with_sgr("    ACTS value unavailable - comparison skipped", CLR_YELLOW_FG))
        return

    print(f"    ACTS: {with_sgr(_fmt(c.acts), STYLE_BOLD)}    diff (ACTS - mean random): "
          f"{_fmt(c.diff_pp, 3)} pp")
    print(f"    Wilcoxon signed-rank (one-sided, ACTS > random): p = {_fmt_p(c.wilcoxon_p)}")
    ci = c.prop_ci or (float('nan'), float('nan'))
    print(f"    P(random >= ACTS): {c.prop_count}/{c.n} = {_fmt(c.prop_ge, 3)}  "
          f"95% Wilson CI [{_fmt(ci[0], 3)}, {_fmt(ci[1], 3)}]")
    print(f"    Vargha-Delaney A12 = {_fmt(c.a12, 3)}")


def run_db_analysis(args: argparse.Namespace) -> None:
    data_dir = Path(args.data_dir)
    root = data_dir.parent
    if not data_dir.is_dir():
        print(f"data_dir not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    equivalent_fps = load_equivalent_fingerprints(data_dir)
    print(f"Loaded {len(equivalent_fps)} equivalent-mutant fingerprint(s).")

    groups = discover_groups(data_dir)
    paired = sorted(s for s, g in groups.items()
                    if g.acts_session is not None and g.random_sessions)
    if not paired:
        print(f"No paired sessions found in {data_dir}.", file=sys.stderr)
        sys.exit(1)

    size_labels = {args.primary_size: "primary, t=2",
                   args.supplementary_size: "supplementary, t=1"}

    all_comparisons: list[MetricComparison] = []

    for size in paired:
        group = groups[size]
        print_size_header(size, size_labels.get(size))

        # ---- score ACTS suite ----
        acts_label = f"acts_{size}"
        assert group.acts_session is not None
        acts_score = score_session(
            group.acts_session, data_dir / f"baseline_{acts_label}_coverage.json",
            equivalent_fps, root, acts_label, size, None,
        )
        # ---- score every random suite ----
        random_scores: dict[int, SuiteScore] = {}
        for seed in sorted(group.random_sessions):
            label = f"random_{size}_s{seed}"
            sc = score_session(
                group.random_sessions[seed],
                data_dir / f"baseline_{label}_coverage.json",
                equivalent_fps, root, label, size, seed,
            )
            if sc is not None:
                random_scores[seed] = sc

        # complete random suites only for inference
        complete = {s: sc for s, sc in random_scores.items() if not sc.pending}
        skipped_pending = sorted(set(random_scores) - set(complete))
        if skipped_pending:
            print(with_sgr(f"\n  Excluded seeds with pending items: {skipped_pending}", CLR_YELLOW_FG))
        if acts_score is not None and acts_score.pending:
            print(with_sgr("  The ACTS session has pending items and is incomplete.", CLR_YELLOW_FG))

        seeds_sorted = sorted(complete)
        cov_arr = np.array([complete[s].covered_score for s in seeds_sorted])
        full_arr = np.array([complete[s].full_score for s in seeds_sorted])

        # ---- branch coverage ----
        acts_branch = branch_coverage(data_dir / f"baseline_{acts_label}.coverage")
        branch_vals = []
        for s in seeds_sorted:
            bc = branch_coverage(data_dir / f"baseline_random_{size}_s{s}.coverage")
            branch_vals.append(bc if bc is not None else float('nan'))
        branch_arr = np.array(branch_vals, dtype=float)

        # ---- H1 / H2 comparisons ----
        print(f"\n{with_sgr('H1 / H2', STYLE_BOLD)}")
        comparisons = [
            compare_metric("Covered mutation score (primary)", size, cov_arr,
                           acts_score.covered_score if acts_score else None, args.alpha),
            compare_metric("Full mutation score", size, full_arr,
                           acts_score.full_score if acts_score else None, args.alpha),
            compare_metric("Branch coverage", size, branch_arr,
                           acts_branch, args.alpha),
        ]
        for c in comparisons:
            print_comparison(c)
        all_comparisons.extend(comparisons)

        # ---- H3 McNemar ----
        print(f"\n{with_sgr('H3 (exact McNemar)', STYLE_BOLD)}")
        if acts_score is None or acts_score.pending:
            print(with_sgr("  ACTS session unavailable/incomplete - H3 skipped.", CLR_YELLOW_FG))
        elif not complete:
            print(with_sgr("  No complete random suite - H3 skipped.", CLR_YELLOW_FG))
        else:
            a_killed = acts_score.killed_fps
            bs, cs = [], []
            for s in seeds_sorted:
                u = acts_score.universe_fps & complete[s].universe_fps
                ak = a_killed & u
                rk = complete[s].killed_fps & u
                bs.append(len(ak - rk))
                cs.append(len(rk - ak))
            mean_b = sum(bs) / len(bs)
            mean_c = sum(cs) / len(cs)
            b = round(mean_b)
            c = round(mean_c)
            p = mcnemar_exact(b, c)
            print(f"  averaged over {len(seeds_sorted)} random seeds:")
            print(f"    mean b (killed only by ACTS)   = {mean_b:.2f}  (rounded: {b})")
            print(f"    mean c (killed only by random) = {mean_c:.2f}  (rounded: {c})")
            print(f"    discordant pairs b+c           = {b + c}")
            print(f"    exact McNemar p                = {_fmt_p(p)}")

        # ---- per-mutant kill-rate distribution ----
        if size == args.supplementary_size and len(complete) >= 2 and acts_score is not None:
            print(f"\n{with_sgr(f'Per-mutant kill-rate distribution (n={len(complete)} random seeds, size {size})', STYLE_BOLD)}")
            universe: set[_Fp] = set()
            for sc in complete.values():
                universe |= sc.universe_fps
            rate = {}
            for fp in universe:
                killed_in = sum(1 for sc in complete.values() if fp in sc.killed_fps)
                rate[fp] = killed_in / len(complete)
            rates = np.array(list(rate.values()))
            edges = [-0.00001, 0.00001, 0.2, 0.4, 0.6, 0.8, 0.99999, 1.00001]
            labels = ["= 0", "(0, 0.2)", "[0.2,0.4)", "[0.4,0.6)",
                      "[0.6,0.8)", "[0.8,1.0)", "= 1.0"]
            counts, _ = np.histogram(rates, bins=edges)
            for lab, cnt in zip(labels, counts):
                print(f"    kill rate {lab:<10}: {cnt}")

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("data_dir", nargs="?", default="test_data",
                   help="directory with cosmicray_*.sqlite and baseline_* files (default: test_data)")
    p.add_argument("--primary-size", type=int, default=456,
                   help="suite size labelled primary / t=2 (default: 456)")
    p.add_argument("--supplementary-size", type=int, default=59,
                   help="suite size labelled supplementary / t=1 (default: 59)")
    p.add_argument("--alpha", type=float, default=0.05,
                   help="significance level for the Wilson confidence interval (default: 0.05)")
    return p


def main() -> None:
    run_db_analysis(build_parser().parse_args())


if __name__ == "__main__":
    main()
