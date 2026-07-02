"""Helps get coverage information. 

Coverage.py's executed_lines only records the first line of each statement. 
Mutations on continuation lines (e.g. arguments on line N+1 of a multi-line 
call) must be mapped to their statement's start line before a coverage lookup, 
otherwise they appear uncovered even when the enclosing statement was executed.
"""
import ast
from pathlib import Path

_statement_map_cache: dict[str, dict[int, int]] = {}

_COMPOUND_STATEMENT_TYPES: tuple[type, ...] = (
    ast.If,
    ast.For,
    ast.While,
    ast.With,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.AsyncFor,
    ast.AsyncWith,
    ast.Try,
    ast.Match,
    ast.TryStar
)

def statement_start_line(source_path: str, line: int) -> int:
    """Return the first line of the simple statement that contains the given line.

    Only maps continuation lines of simple (non-compound) statements. Compound statements are excluded because coverage.py tracks their body lines individually.
    Returns line unchanged if it cannot be mapped.
    """
    if source_path not in _statement_map_cache:
        try:
            source = Path(source_path).read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            _statement_map_cache[source_path] = {}
        else:
            mapping: dict[int, int] = {}
            for node in ast.walk(tree):
                if isinstance(node, ast.stmt) and not isinstance(node, _COMPOUND_STATEMENT_TYPES):
                    start = node.lineno
                    end = getattr(node, "end_lineno", node.lineno)
                    for ln in range(start, end + 1):
                        if ln not in mapping:
                            mapping[ln] = start
            _statement_map_cache[source_path] = mapping
    return _statement_map_cache[source_path].get(line, line)


def is_covered_abs(module_abs: str, line: int, covered: dict[str, set[int]]) -> bool:
    """Return True if line in the already-resolved module_abs path is covered."""
    if module_abs not in covered:
        return False
    covered_lines = covered[module_abs]
    if line in covered_lines:
        return True
    return statement_start_line(module_abs, line) in covered_lines


def is_covered(module_path: str, line: int, covered: dict[str, set[int]], root: Path) -> bool:
    """Return True if line in module_path (relative to root) is covered."""
    return is_covered_abs(str((root / module_path).resolve()), line, covered)
