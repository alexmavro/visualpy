"""LLM-based summarization — feed AST structure, get non-technical descriptions."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from visualpy.models import AnalyzedProject, AnalyzedScript

DEFAULT_MODEL = "gemini/gemini-2.5-flash"

_SYSTEM_PROMPT = (
    "You are a technical writer who explains software to non-technical business "
    "stakeholders. You write clear, jargon-free summaries. You never mention "
    "programming concepts like functions, variables, loops, or imports. Instead, "
    "describe what the script accomplishes in business terms."
)


def summarize_script(
    script: AnalyzedScript, model: str | None = None
) -> str | None:
    """Generate a plain-English summary for a single script."""
    model = model or os.environ.get("VISUALPY_MODEL", DEFAULT_MODEL)
    messages = _build_script_prompt(script)
    return _call_llm(messages, model)


def summarize_project(
    project: AnalyzedProject, model: str | None = None
) -> str | None:
    """Generate an executive summary for the entire project."""
    model = model or os.environ.get("VISUALPY_MODEL", DEFAULT_MODEL)
    messages = _build_project_prompt(project)
    return _call_llm(messages, model)


def _build_script_prompt(script: AnalyzedScript) -> list[dict]:
    """Format a script's structured data into LLM messages."""
    triggers = ", ".join(f"{t.type}: {t.detail}" for t in script.triggers) or "None"
    services = ", ".join(s.name for s in script.services) or "None"
    secrets = ", ".join(script.secrets) or "None"

    # Group steps by function
    steps_by_func: dict[str, list[str]] = {}
    for step in script.steps:
        key = step.function_name or "(top-level)"
        steps_by_func.setdefault(key, []).append(
            f"- [{step.type}] {step.description}"
        )

    steps_text = ""
    for func, lines in steps_by_func.items():
        steps_text += f"\nIn {func}:\n" + "\n".join(lines) + "\n"

    if not steps_text.strip():
        steps_text = "No steps detected."

    user_msg = (
        f"Objective: Write a 1-2 sentence plain-English summary of what this "
        f"automation script does.\n\n"
        f"Script: {script.path}\n"
        f"Entry point: {'Yes' if script.is_entry_point else 'No'}\n"
        f"Triggers: {triggers}\n"
        f"Services used: {services}\n"
        f"Secrets/API keys needed: {secrets}\n\n"
        f"Steps (in execution order):\n{steps_text}\n"
        f"Instructions:\n"
        f"- Describe what this script accomplishes, not how it works\n"
        f"- Mention the key services and data sources by name\n"
        f"- Keep it under 2 sentences\n"
        f"- Write for someone who has never seen code before\n\n"
        f"Expected Output: A 1-2 sentence plain-English description."
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def _build_project_prompt(project: AnalyzedProject) -> list[dict]:
    """Format a project's structured data into LLM messages."""
    services = ", ".join(s.name for s in project.services) or "None"
    entry_points = ", ".join(project.entry_points) or "None"

    script_lines = []
    for s in project.scripts:
        desc = s.summary or "No summary available"
        script_lines.append(f"- {s.path}: {desc}")
    scripts_text = "\n".join(script_lines) or "No scripts."

    conn_lines = []
    for c in project.connections:
        conn_lines.append(f"- {c.source} -> {c.target}: {c.detail}")
    conns_text = "\n".join(conn_lines) or "No connections."

    user_msg = (
        f"Objective: Write a 2-3 sentence executive summary of this automation "
        f"project.\n\n"
        f"Project: {project.path}\n"
        f"Scripts: {len(project.scripts)}\n"
        f"Services: {services}\n"
        f"Entry points: {entry_points}\n\n"
        f"Script summaries:\n{scripts_text}\n\n"
        f"Connections between scripts:\n{conns_text}\n\n"
        f"Instructions:\n"
        f"- Describe the overall purpose of this project as a system\n"
        f"- Mention how the scripts work together\n"
        f"- Highlight the main services and data flows\n"
        f"- Keep it under 3 sentences\n"
        f"- Write for a business stakeholder, not a developer\n\n"
        f"Expected Output: A 2-3 sentence executive summary."
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


def _call_llm(messages: list[dict], model: str) -> str | None:
    """Call the LLM via litellm. Returns None on any failure."""
    try:
        import litellm
    except ImportError:
        print(
            "[visualpy] Warning: litellm not installed. "
            "Install with: pip install visualpy[llm]",
            file=sys.stderr,
        )
        return None

    litellm.suppress_debug_info = True

    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            max_tokens=200,
            # Omit temperature — lets litellm use each provider's default.
            # Avoids known issues with models that misbehave at low temps.
        )
        content = response.choices[0].message.content
        if not content or not content.strip():
            return None
        return content.strip()
    except Exception as exc:
        print(f"[visualpy] Warning: LLM call failed: {exc}", file=sys.stderr)
        return None
