"""Data models for visualpy analysis output."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Service:
    """An external service detected via imports."""

    name: str  # "Google Sheets"
    library: str  # "gspread"
    icon: str | None = None


@dataclass
class Trigger:
    """How a script gets invoked."""

    type: str  # "cron", "webhook", "cli", "manual", "import"
    detail: str  # "*/5 * * * *" or "POST /webhook/intake"


@dataclass
class Step:
    """A single operation within a script."""

    line_number: int
    type: str  # "api_call", "file_io", "db_op", "transform", "decision", "output"
    description: str  # "Fetches leads from Google Maps API"
    function_name: str | None = None
    service: Service | None = None
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


@dataclass
class ScriptConnection:
    """A relationship between two scripts in a project."""

    source: str  # script path
    target: str  # script path
    type: str  # "import", "file_io", "subprocess", "trigger"
    detail: str  # "cleanup.py writes clean.csv -> upload.py reads clean.csv"


@dataclass
class AnalyzedScript:
    """Analysis result for a single Python file."""

    path: str  # relative to project root
    is_entry_point: bool = False
    steps: list[Step] = field(default_factory=list)
    imports_internal: list[str] = field(default_factory=list)
    imports_external: list[str] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    triggers: list[Trigger] = field(default_factory=list)
    signature: dict | None = None  # main() type hints
    summary: str | None = None  # LLM-generated plain English


@dataclass
class AnalyzedProject:
    """Analysis result for an entire project folder."""

    path: str
    scripts: list[AnalyzedScript] = field(default_factory=list)
    connections: list[ScriptConnection] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
