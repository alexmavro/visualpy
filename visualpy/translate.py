"""Deterministic translation of analysis output into business-friendly language."""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING

from visualpy.models import Step, Trigger

if TYPE_CHECKING:
    from visualpy.models import AnalyzedScript

# --- Type labels -----------------------------------------------------------

BUSINESS_LABELS: dict[str, str] = {
    "api_call": "External Service",
    "file_io": "Read/Write File",
    "db_op": "Database",
    "decision": "Check",
    "output": "Log/Notify",
    "transform": "Data Processing",
}

TECHNICAL_LABELS: dict[str, str] = {
    "api_call": "API Call",
    "file_io": "File I/O",
    "db_op": "Database",
    "decision": "Decision",
    "output": "Output",
    "transform": "Transform",
}

# Short forms for compact cards (same as current script_card.html).
TECHNICAL_LABELS_SHORT: dict[str, str] = {
    "api_call": "API",
    "file_io": "File",
    "db_op": "DB",
    "decision": "Decision",
    "output": "Output",
    "transform": "Transform",
}

# --- Step translation -------------------------------------------------------

# api_call: method hints → verb
_API_VERBS: list[tuple[str, str]] = [
    (".post(", "Sends data to"),
    (".put(", "Updates data on"),
    (".patch(", "Updates data on"),
    (".delete(", "Removes data from"),
    ("authorize(", "Authenticates with"),
]
# default for .get() and anything else → "Fetches data from"


def translate_step(step: Step) -> str:
    """Return a plain-English one-liner for a step."""
    desc = step.description
    svc_name = step.service.name if step.service else None

    if step.type == "api_call":
        return _translate_api(desc, svc_name)
    if step.type == "file_io":
        return _translate_file(desc)
    if step.type == "db_op":
        return _translate_db(desc)
    if step.type == "decision":
        return _translate_decision(desc)
    if step.type == "output":
        return _translate_output(desc)
    if step.type == "transform":
        return _translate_transform(desc)
    return BUSINESS_LABELS.get(step.type, step.type.replace("_", " ").capitalize())


def _translate_api(desc: str, svc_name: str | None) -> str:
    target = svc_name or "external service"
    for pattern, verb in _API_VERBS:
        if pattern in desc:
            return f"{verb} {target}"
    return f"Fetches data from {target}"


def _translate_file(desc: str) -> str:
    dl = desc.lower()
    # Write signals
    if any(kw in dl for kw in (".dump(", ".to_csv", ".to_json", ".to_excel",
                                ".write(", ".write_text(", "'w'", "\"w\"")):
        return "Saves data to file"
    # Read signals
    if any(kw in dl for kw in (".load(", ".read_csv", ".read_json", ".read_excel",
                                ".read(", ".read_text(", "'r'", "\"r\"")):
        return "Reads data from file"
    if "open()" in dl or "open(" in dl:
        return "Opens file"
    return "Reads/writes file"


def _translate_db(desc: str) -> str:
    dl = desc.lower()
    if any(kw in dl for kw in (".insert", ".add(", ".commit(", ".update(",
                                ".create(", ".save(")):
        return "Saves to database"
    return "Queries database"


def _translate_decision(desc: str) -> str:
    if desc.startswith("try/except"):
        return "Handles potential errors"
    if desc.startswith("for "):
        # "for target in iter_expr" or "for (k, v) in ..." → "Processes each target/k"
        m = re.match(r"for\s+\(?(\w+)", desc)
        if m:
            return f"Processes each {m.group(1)}"
        return "Repeats for each item"
    if desc.startswith("while "):
        return "Repeats while condition is met"
    if desc.startswith("if "):
        # Strip the "if " prefix, simplify
        condition = desc[3:].strip()
        return f"Checks: {_simplify_condition(condition)}"
    return "Checks a condition"


def _simplify_condition(cond: str) -> str:
    """Best-effort simplification of if-conditions for business readers."""
    # "not X" → "X is missing"
    if cond.startswith("not "):
        subject = cond[4:].strip()
        # "not os.path.exists(...)" → "file doesn't exist"
        if "os.path.exists" in subject or "Path(" in subject:
            return "file doesn't exist"
        return f"{_clean_var(subject)} is missing"
    # "X is None" → "X is empty"
    if " is None" in cond:
        subject = cond.split(" is None")[0].strip()
        return f"{_clean_var(subject)} is empty"
    # Clean up code-like patterns for business readers
    cleaned = _humanize_condition(cond)
    # Truncate long conditions
    if len(cleaned) > 60:
        return cleaned[:57] + "..."
    return cleaned


def _humanize_condition(cond: str) -> str:
    """Turn code-like conditions into natural language."""
    result = cond
    # dict access: item['matched'] → "item matched"
    result = re.sub(r"(\w+)\[(['\"])(\w+)\2\]", r"\1 \3", result)
    # .get() calls: item.get('needs_review') → "item needs review"
    result = re.sub(r"(\w+)\.get\((['\"])(\w+)\2\)", r"\1 \3", result)
    # Clean up parentheses and connectors
    result = result.replace(" and (not ", " and not ")
    result = re.sub(r"[()]", "", result)
    # Replace underscores in variable-like tokens with spaces
    result = re.sub(r"\b(\w+_\w+)\b", lambda m: m.group(1).replace("_", " "), result)
    # If still looks like code (dots, brackets), fall back
    if any(c in result for c in (".", "[", "]", "{", "}")):
        return "data meets conditions"
    cleaned = result.strip()
    return cleaned if cleaned else "data meets conditions"


def _clean_var(name: str) -> str:
    """Strip common prefixes and make variable names slightly more readable."""
    # Strip self. prefix
    if name.startswith("self."):
        name = name[5:]
    # Strip leading underscores
    name = name.lstrip("_")
    return name or "value"


def _translate_output(desc: str) -> str:
    dl = desc.lower()
    if "logger." in dl or "logging." in dl:
        if "error" in dl:
            return "Records an error"
        if "warning" in dl:
            return "Records a warning"
        return "Records activity"
    if "print(" in dl:
        return "Displays message"
    if "send" in dl:
        return "Sends notification"
    return "Produces output"


def _translate_transform(desc: str) -> str:
    dl = desc.lower()
    if "list comprehension" in dl or "dict comprehension" in dl or "set comprehension" in dl:
        return "Builds a collection of items"
    if ".split(" in dl:
        return "Splits text into parts"
    if ".join(" in dl:
        return "Joins text together"
    if ".strip(" in dl or ".lower(" in dl or ".upper(" in dl or ".replace(" in dl:
        return "Cleans up text"
    if "sorted(" in dl:
        return "Sorts data"
    if "int(" in dl or "float(" in dl or "str(" in dl:
        return "Converts data type"
    if "len(" in dl:
        return "Counts items"
    if ".encode(" in dl or ".decode(" in dl:
        return "Converts text encoding"
    if ".loads(" in dl or ".dumps(" in dl:
        return "Converts data format"
    return "Processes data"


# --- Trigger translation ----------------------------------------------------

# Common cron schedules
_CRON_PATTERNS: list[tuple[str, str]] = [
    ("* * * * *", "Runs every minute"),
    ("0 * * * *", "Runs every hour"),
    ("0 0 * * *", "Runs daily at midnight"),
    ("0 0 * * 0", "Runs weekly on Sunday"),
    ("0 0 1 * *", "Runs monthly"),
]

_CRON_INTERVAL = re.compile(r"^\*/(\d+)\s")


def translate_trigger(trigger: Trigger) -> str:
    """Return a plain-English description for a trigger."""
    detail = trigger.detail
    ttype = trigger.type.lower()

    if ttype == "cron" or ttype == "schedule":
        return _translate_cron(detail)
    if ttype == "cli":
        return _translate_cli(detail)
    if ttype == "webhook":
        return _translate_webhook(detail)
    if ttype == "import":
        return "Used by other scripts"
    if ttype == "manual":
        return "Run manually"
    return trigger.type.capitalize()


def _translate_cron(detail: str) -> str:
    for pattern, human in _CRON_PATTERNS:
        if pattern in detail:
            return human
    m = _CRON_INTERVAL.match(detail)
    if m:
        interval = int(m.group(1))
        return f"Runs every {interval} minutes"
    return "Runs on a schedule"


def _translate_cli(detail: str) -> str:
    if "__main__" in detail:
        return "Can be run directly"
    if "argparse" in detail:
        return "Accepts command-line options"
    if "click" in detail or "typer" in detail:
        dl = detail.lower()
        # "click: command_name" → "Command: command_name"
        for prefix in ("click:", "typer:"):
            if prefix in dl:
                name = detail.split(":", 1)[-1].strip()
                if name:
                    return f"Command: {name}"
        return "Run from command line"
    return "Run from command line"


def _translate_webhook(detail: str) -> str:
    if "modal" in detail.lower():
        # "modal endpoint: name" → "Cloud function: name"
        name = detail.split(":", 1)[-1].strip() if ":" in detail else detail
        return f"Cloud function: {name}"
    # "POST /path" or "/path"
    path = detail
    for method in ("POST ", "GET ", "PUT ", "DELETE ", "PATCH "):
        if detail.upper().startswith(method):
            path = detail[len(method):].strip()
            break
    if path:
        return f"Triggered by web request to {path}"
    return "Triggered by web request"


# --- Secret translation -----------------------------------------------------

_SECRET_PREFIXES: list[tuple[str, str]] = [
    ("AWS_", "AWS"),
    ("GOOGLE_", "Google"),
    ("OPENAI_", "OpenAI"),
    ("ANTHROPIC_", "Anthropic"),
    ("APIFY_", "Apify"),
    ("SLACK_", "Slack"),
    ("PANDADOC_", "PandaDoc"),
    ("INSTANTLY_", "Instantly"),
    ("STRIPE_", "Stripe"),
    ("TWILIO_", "Twilio"),
    ("SENDGRID_", "SendGrid"),
    ("GITHUB_", "GitHub"),
    ("GITLAB_", "GitLab"),
    ("AZURE_", "Azure"),
    ("HF_", "Hugging Face"),
    ("HUGGINGFACE_", "Hugging Face"),
]

_SECRET_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_CREDENTIALS", "_PASSWORD")


def translate_secret(secret: str) -> str:
    """Return a plain-English label for a secret/env var name."""
    upper = secret.upper()

    # Check known prefixes first
    for prefix, label in _SECRET_PREFIXES:
        if upper.startswith(prefix):
            return f"{label} credentials"

    # Check generic suffixes
    for suffix in _SECRET_SUFFIXES:
        if upper.endswith(suffix):
            name = secret[: -len(suffix)].replace("_", " ").strip().title()
            if name:
                return f"{name} credentials"
            return "API credentials"

    return f"Configuration: {secret}"


# --- Connection type translation --------------------------------------------

_CONNECTION_LABELS: dict[str, str] = {
    "import": "uses",
    "file_io": "shares data with",
    "subprocess": "launches",
    "trigger": "triggers",
}


def translate_connection(conn_type: str) -> str:
    """Return a business-friendly verb for a connection type."""
    return _CONNECTION_LABELS.get(conn_type, conn_type)


# --- Phase inference --------------------------------------------------------

PHASE_LABELS: dict[str, str] = {
    "setup": "Setup & Data Gathering",
    "processing": "Data Processing",
    "storage": "Storage & Delivery",
    "error_handling": "Error Handling",
    "reporting": "Reporting",
}

PHASE_ORDER: list[str] = ["setup", "processing", "storage", "error_handling", "reporting"]

# Keywords that signal write/storage intent.
_STORAGE_KEYWORDS = (
    ".post(", ".put(", ".patch(", ".delete(",
    "send(", ".dump(", ".to_csv", ".to_json", ".to_excel",
    ".write(", ".write_text(", "'w'", '"w"',
    ".insert(", ".add(", ".commit(", ".create(", ".save(", ".update(",
)

# Keywords that signal read/setup intent.
_SETUP_KEYWORDS = (
    "authorize(", "authenticate(", "connect(",
    ".load(", ".read_csv", ".read_json", ".read_excel",
    ".read(", ".read_text(", "'r'", '"r"',
    "open(", ".get(",
)


def infer_phase(step: Step) -> str:
    """Infer the business phase of a step from its type and description."""
    desc = (step.description or "").lower()

    # Error handling is always its own phase.
    if step.type == "decision" and desc.startswith("try/except"):
        return "error_handling"

    # Loops are processing.
    if step.type == "decision" and (desc.startswith("for ") or desc.startswith("while ")):
        return "processing"

    # Output steps are reporting.
    if step.type == "output":
        return "reporting"

    # Transforms are processing.
    if step.type == "transform":
        return "processing"

    # For api_call, file_io, db_op — check description keywords.
    if any(kw in desc for kw in _STORAGE_KEYWORDS):
        return "storage"
    if any(kw in desc for kw in _SETUP_KEYWORDS):
        return "setup"

    # Generic decisions (if conditions) default to processing.
    if step.type == "decision":
        return "processing"

    # Default: setup for api_call/file_io/db_op, processing for anything else.
    if step.type in ("api_call", "file_io", "db_op"):
        return "setup"
    return "processing"


def deduplicate_steps(steps: list[Step]) -> list[tuple[str, list[Step]]]:
    """Group steps with identical ``translate_step()`` descriptions.

    Returns ``(description, [steps])`` tuples in first-occurrence order.
    Groups of 1 render normally; groups of 2+ collapse into a summary with
    an expandable list.
    """
    groups: dict[str, list[Step]] = {}
    for step in steps:
        try:
            key = translate_step(step)
        except Exception:
            key = step.description or "Unknown step"
        groups.setdefault(key, []).append(step)
    return list(groups.items())


def explain_pattern(desc: str, steps: list[Step]) -> str:
    """Generate a teaching insight for a group of identical steps.

    Called by the template when a dedup group has N > 1 steps.  Returns a
    short sentence that explains *why* this pattern exists rather than just
    repeating the description.  Never raises — returns a safe fallback on
    any error to avoid crashing the template.
    """
    try:
        return _explain_pattern_inner(desc, steps)
    except Exception:
        try:
            n = len(steps) if steps else 0
        except Exception:
            n = 0
        return f"Repeated pattern \u2014 this appears {n} times across the script"


def _explain_pattern_inner(desc: str, steps: list[Step]) -> str:
    n = len(steps)
    dl = desc.lower()

    # --- Output / logging patterns ---
    if "displays message" in dl:
        if n > 10:
            return (
                f"Excessive output \u2014 {n} print() calls; consider Python\u2019s "
                "logging module for structured output"
            )
        return f"Status logging \u2014 tracks workflow progress across {n} checkpoints"
    if any(kw in dl for kw in ("records activity", "records a warning",
                                "records an error", "produces output")):
        return f"Status logging \u2014 tracks workflow progress across {n} checkpoints"
    if "sends notification" in dl:
        return f"Notification system \u2014 alerts stakeholders at {n} different stages"

    # --- Error-handling patterns ---
    if "handles potential errors" in dl:
        if n > 5:
            return (
                "Repetitive error handling \u2014 "
                f"{n} identical try/except blocks suggest extracting a shared helper"
            )
        return (
            "Defensive coding \u2014 each operation is protected so one failure "
            "doesn\u2019t crash the script"
        )

    # --- API patterns (extract service name after "from"/"to") ---
    if "fetches data from" in dl:
        svc = desc.split("from ", 1)[-1] if "from " in desc else "service"
        return f"Batch data gathering \u2014 collects data from {svc} in {n} requests"
    if "sends data to" in dl or "updates data on" in dl:
        for prep in ("to ", "on "):
            if prep in desc.lower():
                svc = desc.split(prep, 1)[-1]
                break
        else:
            svc = "service"
        return f"Batch updates \u2014 pushes data to {svc} in {n} operations"
    if "authenticates with" in dl:
        return f"Multi-service authentication \u2014 connects to {n} different services"

    # --- Database patterns ---
    if "saves to database" in dl:
        return f"Incremental storage \u2014 saves results in {n} operations as they\u2019re processed"
    if "queries database" in dl:
        return f"Multi-query retrieval \u2014 retrieves different data sets in {n} queries"

    # --- File I/O patterns ---
    if "saves data to file" in dl:
        return f"Progressive file output \u2014 writes data across {n} save operations"
    if "reads data from file" in dl:
        return f"Multi-source input \u2014 loads data from {n} different reads"

    # --- Decision patterns ---
    if "processes each" in dl or "repeats for each" in dl:
        return f"Iteration pattern \u2014 {n} loops process data through multiple stages"
    if "checks:" in dl:
        return f"Validation logic \u2014 verifies {n} conditions to ensure correct behavior"

    # --- Transform patterns ---
    if any(kw in dl for kw in ("processes data", "builds a collection",
                                "cleans up text", "sorts data",
                                "converts data", "counts items",
                                "splits text", "joins text")):
        return f"Data pipeline \u2014 transforms data through {n} processing steps"

    # --- Generic fallback by step type ---
    step_type = steps[0].type if steps else "unknown"
    label = BUSINESS_LABELS.get(step_type, step_type.replace("_", " ").capitalize())
    return f"Repeated {label} \u2014 this pattern appears {n} times across the script"


def group_steps_by_phase(steps: list[Step]) -> list[tuple[str, str, list[Step]]]:
    """Group steps by inferred phase, ordered by PHASE_ORDER.

    Returns a list of ``(phase_key, phase_label, steps)`` tuples.
    Empty phases are omitted.
    """
    buckets: dict[str, list[Step]] = {}
    for step in steps:
        phase = infer_phase(step)
        buckets.setdefault(phase, []).append(step)

    result = []
    for phase_key in PHASE_ORDER:
        if phase_key in buckets:
            result.append((phase_key, PHASE_LABELS[phase_key], buckets[phase_key]))
    # Include any phases not in PHASE_ORDER (defensive).
    for phase_key, phase_steps in buckets.items():
        if phase_key not in PHASE_ORDER:
            label = phase_key.replace("_", " ").capitalize()
            result.append((phase_key, label, phase_steps))
    return result


# --- Anti-pattern detection (Sprint 8) ------------------------------------------


def detect_antipatterns(script: "AnalyzedScript") -> list[dict]:
    """Detect code quality anti-patterns. Deterministic, zero LLM cost.

    Returns a list of finding dicts with keys: id, severity, title, detail, count.
    Exception-safe — never raises.
    """
    try:
        return _detect_antipatterns_inner(script)
    except Exception as exc:
        print(
            f"[visualpy] Warning: detect_antipatterns failed for "
            f"{getattr(script, 'path', '?')}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []


def _detect_antipatterns_inner(script: "AnalyzedScript") -> list[dict]:
    findings: list[dict] = []
    steps = script.steps
    if not steps:
        return findings

    total = len(steps)

    # Rule: print_spam — many print() calls with no logging framework
    print_steps = [
        s for s in steps
        if s.type == "output" and "print" in s.description.lower()
    ]
    logger_steps = [
        s for s in steps
        if s.type == "output"
        and ("logger" in s.description.lower() or "logging" in s.description.lower())
    ]
    if len(print_steps) > 3 and not logger_steps:
        findings.append({
            "id": "print_spam",
            "severity": "warning",
            "title": "No logging framework",
            "detail": (
                f"{len(print_steps)} print() calls found. Python\u2019s logging module "
                "provides log levels, timestamps, and configurable output."
            ),
            "count": len(print_steps),
        })

    # Rule: phase_imbalance — one phase dominates the script
    phases = group_steps_by_phase(steps)
    for phase_key, phase_label, phase_steps in phases:
        ratio = len(phase_steps) / total
        if ratio > 0.5:
            findings.append({
                "id": "phase_imbalance",
                "severity": "info",
                "title": f"{phase_label} dominates",
                "detail": (
                    f"{phase_label} accounts for {int(ratio * 100)}% of all steps "
                    f"({len(phase_steps)}/{total}). This phase may be doing too much."
                ),
                "phase": phase_key,
                "count": len(phase_steps),
            })

    # Rule: error_handling_bulk — too many identical try/except blocks
    error_steps = [
        s for s in steps
        if s.type == "decision" and s.description.startswith("try/except")
    ]
    if len(error_steps) > 5:
        findings.append({
            "id": "error_handling_bulk",
            "severity": "warning",
            "title": "Repetitive error handling",
            "detail": (
                f"{len(error_steps)} try/except blocks. Consider extracting "
                "a retry/error-handling helper function."
            ),
            "count": len(error_steps),
        })

    # Rule: no_error_handling — script with many steps but zero try/except
    if total > 10 and not error_steps:
        api_or_io = [
            s for s in steps if s.type in ("api_call", "file_io", "db_op")
        ]
        if api_or_io:
            findings.append({
                "id": "no_error_handling",
                "severity": "concern",
                "title": "No error handling",
                "detail": (
                    "This script has no try/except blocks. External service calls "
                    "and file operations should be wrapped in error handling."
                ),
                "count": 0,
            })

    # Rule: transform_heavy — massive identical transform groups
    transform_steps = [s for s in steps if s.type == "transform"]
    if transform_steps:
        for desc, group in deduplicate_steps(transform_steps):
            if len(group) > 15:
                findings.append({
                    "id": "transform_heavy",
                    "severity": "info",
                    "title": "Heavy data manipulation",
                    "detail": (
                        f'"{desc}" appears {len(group)} times. Complex transform '
                        "chains may benefit from a data pipeline library (pandas, etc.)."
                    ),
                    "count": len(group),
                })

    return findings


def compute_health(script: "AnalyzedScript") -> dict:
    """Compute script health summary for template use. Exception-safe."""
    try:
        return _compute_health_inner(script)
    except Exception as exc:
        print(
            f"[visualpy] Warning: compute_health failed for "
            f"{getattr(script, 'path', '?')}: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return {"score": "clean", "color": "green", "findings": []}


def _compute_health_inner(script: "AnalyzedScript") -> dict:
    findings = detect_antipatterns(script)
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    concerns = sum(1 for f in findings if f["severity"] == "concern")

    if concerns > 0:
        return {"score": "needs attention", "color": "red", "findings": findings}
    if warnings >= 2:
        return {"score": "has issues", "color": "amber", "findings": findings}
    if warnings == 1:
        return {"score": "minor issues", "color": "yellow", "findings": findings}
    return {"score": "clean", "color": "green", "findings": findings}
