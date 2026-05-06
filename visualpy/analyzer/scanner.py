"""Project scanner — walk folder, find .py files, detect entry points."""

from __future__ import annotations

import sys
from pathlib import Path

from visualpy.analyzer._constants import SKIP_DIRS as _SKIP_DIRS
from visualpy.analyzer.ast_parser import analyze_file, collect_local_modules
from visualpy.models import AnalyzedScript


def scan_project(path: Path) -> list[AnalyzedScript]:
    """Walk a directory and analyze all Python files.

    Skips common non-source directories and empty __init__.py files.
    If path is a single .py file, analyzes just that file.
    Returns scripts sorted by relative path.
    """
    path = path.resolve()

    if path.is_file() and path.suffix == ".py":
        return [analyze_file(path, path.parent)]

    if not path.is_dir():
        return []

    local_modules = collect_local_modules(path)
    scripts: list[AnalyzedScript] = []
    for py_file in _find_py_files(path):
        try:
            scripts.append(analyze_file(py_file, path, local_modules))
        except Exception as exc:
            rel = py_file.relative_to(path) if py_file.is_relative_to(path) else py_file
            print(f"[visualpy] Warning: failed to analyze {rel}: {exc}", file=sys.stderr)

    return sorted(scripts, key=lambda s: s.path)


def _find_py_files(root: Path, _seen: set[str] | None = None) -> list[Path]:
    """Recursively find .py files, skipping non-source directories.

    Tracks resolved paths to avoid symlink loops.
    """
    if _seen is None:
        _seen = set()

    try:
        real = str(root.resolve())
    except OSError:
        return []
    if real in _seen:
        return []
    _seen.add(real)

    files: list[Path] = []

    try:
        entries = sorted(root.iterdir())
    except (OSError, PermissionError) as exc:
        print(f"[visualpy] Warning: cannot read directory {root}: {exc}", file=sys.stderr)
        return []

    for item in entries:
        try:
            if item.is_dir():
                if item.name in _SKIP_DIRS or item.name.startswith("."):
                    continue
                files.extend(_find_py_files(item, _seen))
            elif item.is_file() and item.suffix == ".py":
                # Skip empty __init__.py
                if item.name == "__init__.py" and item.stat().st_size == 0:
                    continue
                files.append(item)
        except OSError:
            continue

    return files
