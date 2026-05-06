"""Shared constants for the analyzer package."""

SKIP_DIRS: frozenset[str] = frozenset({
    "__pycache__", ".venv", "venv", ".git", "node_modules",
    ".tox", ".mypy_cache", ".pytest_cache", ".eggs", "dist", "build",
})
