"""LLM-based summarization — feed AST structure, get non-technical descriptions."""

from __future__ import annotations

import json as _json
import os
import re
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from visualpy.models import AnalyzedProject, AnalyzedScript, Step

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


def summarize_phases(
    script: AnalyzedScript, model: str | None = None,
) -> tuple[dict[str, str], dict[int, str]] | None:
    """Generate per-phase summaries and contextual step descriptions.

    Returns ``(phase_summaries, contextual_steps)`` or ``None`` if every phase
    failed.  Partial success returns partial results.
    """
    from visualpy.translate import group_steps_by_phase

    model = model or os.environ.get("VISUALPY_MODEL", DEFAULT_MODEL)
    phases = group_steps_by_phase(script.steps)
    if not phases:
        return None

    phase_summaries: dict[str, str] = {}
    contextual_steps: dict[int, str] = {}

    for phase_key, phase_label, steps in phases:
        summary, step_descs = _summarize_single_phase(
            script, phase_key, phase_label, steps, model
        )
        if summary:
            phase_summaries[phase_key] = summary
        contextual_steps.update(step_descs)

    if not phase_summaries and not contextual_steps:
        return None
    return phase_summaries, contextual_steps


def _summarize_single_phase(
    script: AnalyzedScript,
    phase_key: str,
    phase_label: str,
    steps: list[Step],
    model: str,
) -> tuple[str | None, dict[int, str]]:
    """Summarize a single phase. Returns ``(summary, {line: desc})``."""
    messages = _build_phase_prompt(script, phase_label, steps)
    raw = _call_llm(messages, model)
    if raw is None:
        return None, {}
    return _parse_phase_response(raw, steps)


def _build_phase_prompt(
    script: AnalyzedScript,
    phase_label: str,
    steps: list[Step],
) -> list[dict]:
    """Build prompt messages for a single phase."""
    services = ", ".join(s.name for s in script.services) or "None"

    step_lines = []
    for step in steps:
        svc = step.service.name if step.service else "none"
        inputs = ", ".join(step.inputs) if step.inputs else "none"
        outputs = ", ".join(step.outputs) if step.outputs else "none"
        step_lines.append(
            f"- Line {step.line_number} [{step.type}]: {step.description}\n"
            f"  Service: {svc} | Inputs: {inputs} | Outputs: {outputs}"
        )
    steps_text = "\n".join(step_lines) or "No steps."

    user_msg = (
        f"Objective: Explain the \"{phase_label}\" phase of this automation script.\n\n"
        f"Script: {script.path}\n"
        f"Services used: {services}\n"
        f"This phase contains {len(steps)} steps:\n\n"
        f"{steps_text}\n\n"
        f"Instructions:\n"
        f"- Write a 1-2 sentence summary of what this phase accomplishes as a whole\n"
        f"- For EACH step (by line number), write a unique 1-sentence description\n"
        f"- Do NOT use generic phrases like \"Handles potential errors\" or "
        f"\"Fetches data from external service\"\n"
        f"- For error handling: name WHAT error is being caught and HOW it is handled\n"
        f"- For API calls: name the SPECIFIC service and what data is being exchanged\n"
        f"- For file operations: name the SPECIFIC file type and purpose\n"
        f"- Mention specific service names (Google Sheets, Slack, etc.) not \"external service\"\n"
        f"- Write for someone who has never seen code before\n\n"
        f"Expected Output (JSON):\n"
        f'{{\n'
        f'  "phase_summary": "1-2 sentence phase summary",\n'
        f'  "steps": {{\n'
        f'    "<line_number>": "Unique description for this step"\n'
        f'  }}\n'
        f'}}'
    )

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]


# Pattern to strip markdown code fences from LLM responses.
_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?\s*```", re.DOTALL)


def _parse_phase_response(
    raw: str, steps: list[Step],
) -> tuple[str | None, dict[int, str]]:
    """Parse LLM JSON response into (phase_summary, {line: description}).

    Handles markdown fences, Gemini thinking-token prefixes, and partial
    results gracefully.
    """
    valid_lines = {s.line_number for s in steps}

    # Strip markdown fences.
    fence_match = _FENCE_RE.search(raw)
    text = fence_match.group(1) if fence_match else raw

    # Strip text before first '{' and after last '}' (thinking tokens, trailing chat).
    brace = text.find("{")
    if brace == -1:
        print(f"[visualpy] Warning: phase response has no JSON object: {raw[:120]}...", file=sys.stderr)
        return None, {}
    rbrace = text.rfind("}")
    if rbrace == -1:
        print(f"[visualpy] Warning: phase response has no closing brace: {raw[:120]}...", file=sys.stderr)
        return None, {}
    text = text[brace:rbrace + 1]

    try:
        data = _json.loads(text)
    except _json.JSONDecodeError:
        print(f"[visualpy] Warning: phase response is not valid JSON: {text[:120]}...", file=sys.stderr)
        return None, {}

    if not isinstance(data, dict):
        print(f"[visualpy] Warning: phase response is not a JSON object: {type(data).__name__}", file=sys.stderr)
        return None, {}

    # Extract phase summary.
    summary = data.get("phase_summary")
    if isinstance(summary, str) and summary.strip():
        summary = summary.strip()
    else:
        summary = None

    # Extract step descriptions.
    step_descs: dict[int, str] = {}
    raw_steps = data.get("steps", {})
    if isinstance(raw_steps, dict):
        for key, desc in raw_steps.items():
            try:
                line = int(key)
            except (ValueError, TypeError):
                continue
            if line in valid_lines and isinstance(desc, str) and desc.strip():
                step_descs[line] = desc.strip()

    return summary, step_descs


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
            max_tokens=2048,
            # Higher than needed for text output (~50 tokens) because some
            # models (Gemini 2.5) use thinking tokens that count against this
            # limit. 2048 accommodates thinking overhead comfortably.
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
