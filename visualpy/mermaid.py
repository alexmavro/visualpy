"""Mermaid.js syntax generation for project and script visualizations."""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import PurePosixPath

from visualpy.models import AnalyzedProject, AnalyzedScript, ScriptConnection, Step
from visualpy.translate import (
    BUSINESS_LABELS,
    PHASE_LABELS,
    PHASE_ORDER,
    infer_phase,
    translate_connection,
    translate_step,
)

# Short labels for step types (used in compact nodes and potentially templates).
_TYPE_LABELS: dict[str, str] = {
    "api_call": "API",
    "file_io": "File I/O",
    "db_op": "DB",
    "decision": "Decision",
    "output": "Output",
    "transform": "Transform",
}

# Step type → Mermaid node shape template.
# Placeholders: {id} = sanitized node ID, {label} = escaped description.
_STEP_SHAPES: dict[str, str] = {
    "api_call": '{id}["{label}"]',
    "file_io": '{id}[/"{label}"/]',
    "db_op": '{id}[("{label}")]',
    "decision": '{id}{{"{label}"}}',
    "output": '{id}(["{label}"])',
    "transform": '{id}[["{label}"]]',
}

# Step type → classDef name (used in :::class shorthand).
_STEP_CLASS: dict[str, str] = {
    "api_call": "api",
    "file_io": "fileio",
    "db_op": "dbop",
    "decision": "decision",
    "output": "output",
    "transform": "transform",
}

# Mermaid classDef declarations — appended to every graph.
_CLASS_DEFS = """\
classDef api fill:#dbeafe,stroke:#2563eb,color:#1e3a5f
classDef fileio fill:#dcfce7,stroke:#16a34a,color:#14532d
classDef dbop fill:#f3e8ff,stroke:#9333ea,color:#3b0764
classDef decision fill:#ffedd5,stroke:#ea580c,color:#7c2d12
classDef output fill:#f3f4f6,stroke:#6b7280,color:#1f2937
classDef transform fill:#ccfbf1,stroke:#0d9488,color:#134e4a
classDef entry fill:#dcfce7,stroke:#16a34a,stroke-width:3px,color:#14532d
classDef compact fill:#f0f4ff,stroke:#6366f1,color:#312e81,stroke-width:2px"""

_SPECIAL_CHARS = re.compile(r"[^a-zA-Z0-9_]")
_WARNED_TYPES: set[str] = set()


def _sanitize_id(text: str) -> str:
    """Convert arbitrary text into a valid Mermaid node ID.

    Replaces non-alphanumeric characters with underscores and prepends ``n_``
    to guarantee the ID starts with a letter.
    """
    return "n_" + _SPECIAL_CHARS.sub("_", text)


def _escape_label(text: str, max_len: int = 60) -> str:
    """Escape Mermaid special characters and truncate long labels.

    Truncation happens before escaping so escape sequences are never split.
    """
    if len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return (
        text.replace("\\", "#bsol;")
        .replace("#", "#35;")
        .replace('"', "#quot;")
        .replace("<", "#lt;")
        .replace(">", "#gt;")
        .replace("|", "#124;")
        .replace("{", "#lbrace;")
        .replace("}", "#rbrace;")
    )


def _step_node(step: Step, script_stem: str, *, business: bool = False) -> str:
    """Generate a Mermaid node definition for a single step."""
    node_id = f"n_{_SPECIAL_CHARS.sub('_', script_stem)}_{step.line_number}"

    if business:
        # Business mode: translated label, no type prefix (shape/color conveys type).
        # Per-step isolation: if translation fails, fall back to raw description.
        try:
            label = _escape_label(translate_step(step))
        except Exception as exc:
            print(f"[visualpy] Warning: translate_step failed for L{step.line_number}: {exc}", file=sys.stderr)
            label = _escape_label(step.description)
    else:
        # Technical mode: type prefix + raw description.
        prefixes = {
            "api_call": "API: ",
            "file_io": "File: ",
            "db_op": "DB: ",
            "decision": "",
            "output": "Output: ",
            "transform": "Transform: ",
        }
        prefix = prefixes.get(step.type, "")
        label = _escape_label(f"{prefix}{step.description}")

    shape_tpl = _STEP_SHAPES.get(step.type)
    if shape_tpl is None:
        if step.type not in _WARNED_TYPES:
            _WARNED_TYPES.add(step.type)
            print(f"[visualpy] Warning: unknown step type {step.type!r}, using default shape", file=sys.stderr)
        shape_tpl = '{id}["{label}"]'
    cls = _STEP_CLASS.get(step.type, "")
    node_def = shape_tpl.format(id=node_id, label=label)
    if cls:
        node_def += f":::{cls}"
    return node_def


def _compact_function_node(
    func_name: str, steps: list[Step], stem: str, *, business: bool = False
) -> str:
    """Generate a single Mermaid node summarising a collapsed function."""
    node_id = f"n_{_SPECIAL_CHARS.sub('_', stem)}_{_SPECIAL_CHARS.sub('_', func_name)}_compact"

    labels = BUSINESS_LABELS if business else _TYPE_LABELS
    counts = Counter(s.type for s in steps)
    # Top 4 types by count, descending.
    top = counts.most_common(4)
    parts = [f"{n} {labels.get(t, t)}" for t, n in top]
    if len(counts) > 4:
        parts.append(f"+{len(counts) - 4} more")
    type_summary = ", ".join(parts)
    total = len(steps)

    display_name = func_name if business else f"{func_name}()"
    raw_label = f"{display_name} — {total} steps ({type_summary})"
    label = _escape_label(raw_label, max_len=100)
    return f'{node_id}[["{label}"]]:::compact'


def importance_score(script: AnalyzedScript, project: AnalyzedProject) -> int:
    """Heuristic importance score for a script within a project.

    Higher = more important. Used to sort scripts in the overview.
    """
    score = 0
    for conn in project.connections:
        if conn.source == script.path:
            score += 1
        if conn.target == script.path:
            score += 1
    if script.path in project.entry_points:
        score += 2
    score += len(script.services)
    score += min(len(script.steps) // 20, 5)
    return score


def project_graph(project: AnalyzedProject, *, business: bool = False) -> str:
    """Generate a Mermaid graph showing scripts as nodes and connections as edges."""
    lines: list[str] = ["graph LR"]

    # Collect scripts by directory for subgraph grouping.
    dir_scripts: dict[str, list[AnalyzedScript]] = {}
    for script in project.scripts:
        parent = str(PurePosixPath(script.path).parent)
        if parent == ".":
            parent = ""
        dir_scripts.setdefault(parent, []).append(script)

    entry_set = set(project.entry_points)

    # Emit nodes, grouped by directory.
    for directory, scripts in sorted(dir_scripts.items()):
        if directory and len(dir_scripts) > 1:
            dir_id = _sanitize_id(directory)
            dir_label = _escape_label(directory)
            lines.append(f'  subgraph {dir_id}["{dir_label}"]')

        for script in scripts:
            sid = _sanitize_id(script.path)
            label = _escape_label(PurePosixPath(script.path).name)
            cls = ":::entry" if script.path in entry_set else ""
            lines.append(f'  {sid}["{label}"]{cls}')

        if directory and len(dir_scripts) > 1:
            lines.append("  end")

    # Emit edges from connections.
    for conn in project.connections:
        src = _sanitize_id(conn.source)
        tgt = _sanitize_id(conn.target)
        edge_label = translate_connection(conn.type) if business else conn.type
        label = _escape_label(edge_label)
        lines.append(f'  {src} -->|"{label}"| {tgt}')

    # Click handlers: navigate to script view.
    for script in project.scripts:
        sid = _sanitize_id(script.path)
        lines.append(f'  click {sid} "/script/{script.path}"')

    lines.append(_CLASS_DEFS)
    return "\n".join(lines)


def script_flow(
    script: AnalyzedScript,
    *,
    compact: bool = False,
    compact_threshold: int = 8,
    business: bool = False,
) -> str:
    """Generate a Mermaid flowchart for a single script's steps.

    When *compact* is True, functions with more than *compact_threshold*
    steps are collapsed into a single summary node.  When *business* is
    True, node labels use plain-English translations instead of raw code
    descriptions.
    """
    lines: list[str] = ["graph TB"]

    if not script.steps:
        node_id = _sanitize_id(script.path + "_empty")
        lines.append(f'  {node_id}["No steps detected"]')
        lines.append(_CLASS_DEFS)
        return "\n".join(lines)

    # Group steps by function_name (pyflowchart NodesGroup pattern).
    func_steps: dict[str, list[Step]] = {}
    for step in script.steps:
        key = step.function_name or "_module_"
        func_steps.setdefault(key, []).append(step)

    stem = PurePosixPath(script.path).stem

    # Emit subgraphs per function.
    click_lines: list[str] = []
    for func_name, steps in func_steps.items():
        # Compact mode: collapse large functions into a single node.
        if compact and func_name != "_module_" and len(steps) > compact_threshold:
            lines.append(f"  {_compact_function_node(func_name, steps, stem, business=business)}")
            continue

        if func_name != "_module_":
            sg_id = _sanitize_id(f"{stem}_{func_name}")
            display_name = func_name if business else func_name + "()"
            label = _escape_label(display_name)
            lines.append(f'  subgraph {sg_id}["{label}"]')

        for step in steps:
            lines.append(f"    {_step_node(step, stem, business=business)}")
            node_id = f"n_{_SPECIAL_CHARS.sub('_', stem)}_{step.line_number}"
            escaped_path = script.path.replace('"', '\\"')
            click_lines.append(
                f'  click {node_id} call showStepDetail("{escaped_path}", {step.line_number})'
            )

        # Sequential edges within the function.
        for i in range(len(steps) - 1):
            id_a = f"n_{_SPECIAL_CHARS.sub('_', stem)}_{steps[i].line_number}"
            id_b = f"n_{_SPECIAL_CHARS.sub('_', stem)}_{steps[i + 1].line_number}"
            lines.append(f"    {id_a} --> {id_b}")

        if func_name != "_module_":
            lines.append("  end")

    lines.extend(click_lines)
    lines.append(_CLASS_DEFS)
    return "\n".join(lines)


# Phase colors for the pedagogical diagram.
_PHASE_CLASSDEFS = """\
classDef phase_setup fill:#dbeafe,stroke:#2563eb,color:#1e3a5f,stroke-width:2px
classDef phase_processing fill:#ccfbf1,stroke:#0d9488,color:#134e4a,stroke-width:2px
classDef phase_storage fill:#dcfce7,stroke:#16a34a,color:#14532d,stroke-width:2px
classDef phase_error_handling fill:#ffedd5,stroke:#ea580c,color:#7c2d12,stroke-width:2px
classDef phase_reporting fill:#f3f4f6,stroke:#6b7280,color:#1f2937,stroke-width:2px"""


def pedagogical_flow(script: AnalyzedScript) -> str:
    """Generate a simple phase-pipeline Mermaid diagram for business view.

    Shows 3-5 large blocks (one per phase) connected by arrows, instead of
    the full 50+ node technical flowchart.
    """
    if not script.steps:
        return 'graph LR\n  empty["No steps detected"]'

    # Count steps per phase.
    phase_counts: dict[str, int] = {}
    for step in script.steps:
        phase = infer_phase(step)
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    # Build nodes in PHASE_ORDER, skip empty phases.
    nodes: list[tuple[str, str]] = []  # (node_id, node_def)
    for phase_key in PHASE_ORDER:
        count = phase_counts.get(phase_key, 0)
        if count == 0:
            continue
        label = PHASE_LABELS.get(phase_key, phase_key)
        step_word = "step" if count == 1 else "steps"
        escaped = _escape_label(label)
        node_id = f"phase_{phase_key}"
        nodes.append((node_id, f'{node_id}["{escaped}\n{count} {step_word}"]:::phase_{phase_key}'))

    lines: list[str] = ["graph LR"]
    for _, node_def in nodes:
        lines.append(f"  {node_def}")

    # Chain nodes with arrows.
    for i in range(len(nodes) - 1):
        lines.append(f"  {nodes[i][0]} --> {nodes[i + 1][0]}")

    lines.append(_PHASE_CLASSDEFS)
    return "\n".join(lines)
