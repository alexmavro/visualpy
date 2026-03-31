"""Cross-file resolver — detect internal imports, shared files, data flow between scripts."""

from __future__ import annotations

from pathlib import Path

from visualpy.models import AnalyzedScript, ScriptConnection


def resolve_connections(
    scripts: list[AnalyzedScript], project_root: Path
) -> list[ScriptConnection]:
    """Find connections between scripts: imports, shared file I/O, subprocess calls.

    Processes the already-analyzed scripts and looks for:
    1. Import connections — script A imports from script B
    2. File I/O connections — script A writes a file that script B reads
    3. Subprocess connections — script A calls script B via subprocess
    """
    connections: list[ScriptConnection] = []

    # Build lookup: module name → script path
    path_to_script = {s.path: s for s in scripts}
    module_to_path = _build_module_map(scripts)

    for script in scripts:
        # 1. Import connections
        for imp in script.imports_internal:
            top_level = imp.split(".")[0]
            target_path = module_to_path.get(top_level)
            if target_path and target_path != script.path:
                connections.append(
                    ScriptConnection(
                        source=script.path,
                        target=target_path,
                        type="import",
                        detail=f"{script.path} imports from {target_path}",
                    )
                )

        # 2. File I/O connections
        _find_file_io_connections(script, scripts, connections)

        # 3. Subprocess connections
        _find_subprocess_connections(script, path_to_script, connections)

    return _deduplicate(connections)


def _build_module_map(scripts: list[AnalyzedScript]) -> dict[str, str]:
    """Map module names to script paths.

    E.g. "scrape_google_maps" → "scrape_google_maps.py"
    """
    module_to_path: dict[str, str] = {}
    for script in scripts:
        stem = Path(script.path).stem
        module_to_path[stem] = script.path
    return module_to_path


def _find_file_io_connections(
    source_script: AnalyzedScript,
    all_scripts: list[AnalyzedScript],
    connections: list[ScriptConnection],
) -> None:
    """Find scripts that share file paths (one writes, another reads)."""
    source_files = _extract_file_paths(source_script)
    if not source_files:
        return

    for other in all_scripts:
        if other.path == source_script.path:
            continue
        other_files = _extract_file_paths(other)
        shared = source_files & other_files
        for f in shared:
            connections.append(
                ScriptConnection(
                    source=source_script.path,
                    target=other.path,
                    type="file_io",
                    detail=f"both access {f}",
                )
            )


def _extract_file_paths(script: AnalyzedScript) -> set[str]:
    """Extract file path strings from file_io steps.

    Primary: reads from step.inputs and step.outputs (structured data).
    Fallback: parses open('path') from description strings.
    """
    paths: set[str] = set()
    for step in script.steps:
        if step.type != "file_io":
            continue

        # Primary: structured inputs/outputs
        for p in step.inputs:
            if _looks_like_file_path(p):
                paths.add(p)
        for p in step.outputs:
            if _looks_like_file_path(p):
                paths.add(p)

        # Fallback: parse from description (for steps without structured data)
        if not (step.inputs or step.outputs):
            desc = step.description
            if "open(" in desc:
                start = desc.find("'")
                end = desc.rfind("'")
                if start != -1 and end > start:
                    paths.add(desc[start + 1 : end])

    return paths


def _looks_like_file_path(s: str) -> bool:
    """Heuristic: does this string look like a file path (has a file extension)?"""
    if s.startswith("http") or len(s) > 256:
        return False
    # Must have a dot followed by 1-6 alphanumeric chars at the end (file extension)
    parts = s.rsplit(".", 1)
    return len(parts) == 2 and 1 <= len(parts[1]) <= 6 and parts[1].isalnum()


def _find_subprocess_connections(
    source_script: AnalyzedScript,
    path_to_script: dict[str, AnalyzedScript],
    connections: list[ScriptConnection],
) -> None:
    """Detect subprocess calls that reference other scripts in the project."""
    for step in source_script.steps:
        if step.type != "api_call":
            continue
        # subprocess.run shows up as a call — check description for .py references
        desc = step.description
        for target_path in path_to_script:
            if target_path in desc:
                connections.append(
                    ScriptConnection(
                        source=source_script.path,
                        target=target_path,
                        type="subprocess",
                        detail=f"{source_script.path} runs {target_path} via subprocess",
                    )
                )


def _deduplicate(connections: list[ScriptConnection]) -> list[ScriptConnection]:
    """Remove duplicate connections (same source, target, type)."""
    seen: set[tuple[str, str, str]] = set()
    result: list[ScriptConnection] = []
    for c in connections:
        key = (c.source, c.target, c.type)
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result
