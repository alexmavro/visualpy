"""CLI commands for visualpy."""

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from visualpy import __version__
from visualpy.analyzer.cross_file import resolve_connections
from visualpy.analyzer.scanner import scan_project
from visualpy.models import AnalyzedProject


def app():
    parser = argparse.ArgumentParser(
        prog="visualpy",
        description="Auto-visualise Python automations for non-technical stakeholders.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze", help="Analyze a folder of Python scripts"
    )
    analyze_parser.add_argument("path", help="Path to folder to analyze")
    analyze_parser.add_argument(
        "--output", "-o", help="Output JSON file (default: stdout)"
    )

    # serve command
    serve_parser = subparsers.add_parser(
        "serve", help="Start web UI for visual exploration"
    )
    serve_parser.add_argument("path", help="Path to folder to analyze")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "analyze":
        _run_analyze(args)

    if args.command == "serve":
        print(f"[visualpy] serve is not yet implemented. Target: {args.path}")
        sys.exit(0)


def _run_analyze(args: argparse.Namespace) -> None:
    """Run the analysis pipeline and output JSON."""
    target = Path(args.path).resolve()

    if not target.exists():
        print(f"[visualpy] Error: path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)

    scripts = scan_project(target)

    if not scripts:
        print(f"[visualpy] No Python files found in: {args.path}", file=sys.stderr)
        sys.exit(1)

    # Resolve cross-file connections
    project_root = target if target.is_dir() else target.parent
    connections = resolve_connections(scripts, project_root)

    # Aggregate project-level data
    all_services = {}
    all_secrets: set[str] = set()
    entry_points: list[str] = []

    for script in scripts:
        for svc in script.services:
            all_services[svc.name] = svc
        all_secrets.update(script.secrets)
        if script.is_entry_point:
            entry_points.append(script.path)

    project = AnalyzedProject(
        path=str(target),
        scripts=scripts,
        connections=connections,
        services=list(all_services.values()),
        secrets=sorted(all_secrets),
        entry_points=sorted(entry_points),
    )

    output = json.dumps(dataclasses.asdict(project), indent=2)

    if args.output:
        try:
            Path(args.output).write_text(output)
        except OSError as exc:
            print(f"[visualpy] Error: could not write output file: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"[visualpy] Analysis written to {args.output}")
    else:
        print(output)
