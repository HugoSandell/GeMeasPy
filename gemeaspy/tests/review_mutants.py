"""Interactive review tool for mutation testing survivors."""

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import gemeaspy

@dataclass
class MutantEntry:
    module_path: str
    line: int
    tags: list[str]
    operator_name: str
    occurrence: int
    diff: str

    def fingerprint(self) -> tuple[str, str, int]:
        return (self.module_path, self.operator_name, self.occurrence)


_HEADER_RE = re.compile(
    r"^=== (?P<module>.+?):(?P<line>\d+)(?P<tags>[^|]*)\| (?P<operator>.+?) #(?P<occurrence>\d+) ===$"
)
""" 
Matches lines like:
    === gemeaspy\\acquisition\\session.py:42 [UNCOVERED] | core/ReplaceComparisonOperator_Eq_Lt #3 ===
"""


def _parse_tags(raw: str) -> list[str]:
    stripped = raw.strip().strip("[]")
    return [t.strip() for t in stripped.split(",") if t.strip()]


def parse_review_file(path: Path) -> list[MutantEntry]:
    entries: list[MutantEntry] = []
    header: dict | None = None
    diff_lines: list[str] = []

    def _flush() -> None:
        if header is None:
            return
        entries.append(MutantEntry(
            module_path=header["module"],
            line=int(header["line"]),
            tags=_parse_tags(header["tags"]),
            operator_name=header["operator"],
            occurrence=int(header["occurrence"]),
            diff="\n".join(diff_lines).strip(),
        ))

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        m = _HEADER_RE.match(raw_line)
        if m:
            _flush()
            header = m.groupdict()
            diff_lines = []
        elif header is not None:
            diff_lines.append(raw_line)

    _flush()
    return entries


def _load_json_list(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_json_list(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
        f.write("\n")


def _fingerprints(entries: list[dict]) -> set[tuple[str, str, int]]:
    return {(e["module_path"], e["operator_name"], e["occurrence"]) for e in entries}


def _display_entry(entry: MutantEntry, index: int, total: int) -> None:
    tag_str = f"  [{', '.join(entry.tags)}]" if entry.tags else ""
    sep = "─" * 72
    print()
    print(sep)
    print(
        f"{f"Mutant {index}/{total}"}  "
        f"{f"{entry.module_path}:{entry.line}"}"
        f"{tag_str}  "
        f"{entry.operator_name} #{str(entry.occurrence)}"
    )
    print()
    if entry.diff:
        diff_lines = []
        for line in entry.diff.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                diff_lines.append(line)
            elif line.startswith("-") and not line.startswith("---"):
                diff_lines.append(line)
            elif line.startswith("@@"):
                diff_lines.append(line)
            else:
                diff_lines.append(line)
        print("\n".join(diff_lines))
    else:
        print("  (no diff available)")


def _prompt_action() -> str:
    """Return one of 'equivalent', 'not_equivalent', 'skip', 'quit'."""
    print()
    print(
        "[e] Equivalent   " +
        "[n] Not equivalent (needs test)   " +
        "[s] Skip   " +
        "[q] Quit"
    )
    while True:
        try:
            choice = input("Action: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return "quit"
        if choice in ("e", "eq", "equivalent"):
            return "equivalent"
        elif choice in ("n", "no", "not", ""):
            return "not_equivalent"
        elif choice in ("s", "skip"):
            return "skip"
        elif choice in ("q", "quit", "exit"):
            return "quit"
        print("  Enter e, n, s, or q.")


def review_file(review_path: Path, equiv_file: Path, not_equiv_file: Path) -> bool:
    """Review one survived_review_*.txt interactively.

    Returns True when the file is fully processed (or has nothing to review),
    False when the user quits early.
    """
    entries = parse_review_file(review_path)
    equiv_entries = _load_json_list(equiv_file)
    not_equiv_entries = _load_json_list(not_equiv_file)

    known = _fingerprints(equiv_entries) | _fingerprints(not_equiv_entries)
    pending = [e for e in entries if e.fingerprint() not in known]

    header_line = f"\n{review_path.name}"
    counts = f"{len(entries)} total, {len(entries) - len(pending)} already resolved, {len(pending)} to review"
    print(f"{header_line}  {counts}")

    if not pending:
        print("  All mutants already resolved.")
        return True

    skipped: set[tuple[str, str, int]] = set()
    marked_equivalent = 0
    not_equivalent_count = 0
    skipped_count = 0

    for i, entry in enumerate(pending, start=1):
        if entry.fingerprint() in skipped:
            continue

        _display_entry(entry, i, len(pending))
        action = _prompt_action()

        if action == "quit":
            print("\nSession ended early. Decisions so far have been saved.")
            return False

        if action == "equivalent":
            print("Reason (why is this equivalent?):")
            try:
                reason = input("Reason: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                reason = ""

            equiv_entries.append({
                "module_path": entry.module_path,
                "operator_name": entry.operator_name,
                "occurrence": entry.occurrence,
                "reason": reason,
            })
            _save_json_list(equiv_file, equiv_entries)
            marked_equivalent += 1
            print("  Saved as equivalent.")

        elif action == "not_equivalent":
            not_equiv_entries.append({
                "module_path": entry.module_path,
                "operator_name": entry.operator_name,
                "occurrence": entry.occurrence,
            })
            _save_json_list(not_equiv_file, not_equiv_entries)
            not_equivalent_count += 1

        elif action == "skip":
            skipped.add(entry.fingerprint())
            skipped_count += 1
            print("  Skipped.")

    print()
    print(
        f"Done: {marked_equivalent} equivalent, "
        f"{not_equivalent_count} needs test, "
        f"{skipped_count} skipped."
    )
    return True


def main() -> None:
    root_dir = Path(gemeaspy.__file__).parent.parent
    data_dir = root_dir / "test_data"
    equiv_file = data_dir / "equivalent_mutants.json"
    not_equiv_file = data_dir / "not_equivalent_mutants.json"

    if not data_dir.is_dir():
        print(f"test_data/ not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1:]:
        generators = [g.strip().lower() for g in sys.argv[1:]]
        review_files = [data_dir / f"survived_review_{g}.txt" for g in generators]
        missing = [str(f) for f in review_files if not f.is_file()]
        if missing:
            for p in missing:
                print(f"File not found: {p}", file=sys.stderr)
            sys.exit(1)
    else:
        review_files = sorted(data_dir.glob("survived_review_*.txt"))
        if not review_files:
            print(f"No review files found in {data_dir}.", file=sys.stderr)
            print("Run 'python -m gemeaspy.tests.mutate <generator>' first.", file=sys.stderr)
            sys.exit(1)

    for review_path in review_files:
        if not review_file(review_path, equiv_file, not_equiv_file):
            break


if __name__ == "__main__":
    main()
