"""CLI commands for visualpy."""

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from visualpy import __version__
from visualpy.analyzer.cross_file import resolve_connections
from visualpy.analyzer.scanner import scan_project
from visualpy.models import (
    AnalyzedProject,
    AnalyzedScript,
    ScriptConnection,
    Service,
    Step,
    Trigger,
)


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
    analyze_parser.add_argument(
        "--summarize",
        action="store_true",
        help="Generate LLM summaries (requires API key, install with pip install visualpy[llm])",
    )

    # serve command
    serve_parser = subparsers.add_parser(
        "serve", help="Start web UI for visual exploration"
    )
    serve_parser.add_argument("path", nargs="?", default=None, help="Path to folder to analyze")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    serve_parser.add_argument(
        "--from-json",
        dest="from_json",
        help="Load pre-computed analysis from JSON file instead of scanning",
    )
    serve_parser.add_argument(
        "--summarize",
        action="store_true",
        help="Generate LLM summaries (requires API key, install with pip install visualpy[llm])",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "analyze":
        _run_analyze(args)

    if args.command == "serve":
        _run_serve(args)


def _build_project(target: Path) -> AnalyzedProject:
    """Run the full analysis pipeline and return an AnalyzedProject."""
    scripts = scan_project(target)

    if not scripts:
        print(f"[visualpy] No Python files found in: {target}", file=sys.stderr)
        sys.exit(1)

    project_root = target if target.is_dir() else target.parent
    connections = resolve_connections(scripts, project_root)

    all_services = {}
    all_secrets: set[str] = set()
    entry_points: list[str] = []

    for script in scripts:
        for svc in script.services:
            all_services[svc.name] = svc
        all_secrets.update(script.secrets)
        if script.is_entry_point:
            entry_points.append(script.path)

    return AnalyzedProject(
        path=str(target),
        scripts=scripts,
        connections=connections,
        services=list(all_services.values()),
        secrets=sorted(all_secrets),
        entry_points=sorted(entry_points),
    )


def _summarize_project(project: AnalyzedProject) -> None:
    """Populate LLM summaries on the project (mutates in place)."""
    from visualpy.summarizer import summarize_data_flow, summarize_phases, summarize_project, summarize_script

    print("[visualpy] Generating summaries...", file=sys.stderr)

    for i, script in enumerate(project.scripts, 1):
        print(
            f"[visualpy]   Script {i}/{len(project.scripts)}: {script.path}",
            file=sys.stderr,
        )
        script.summary = summarize_script(script)
        result = summarize_phases(script)
        if result:
            script.phase_summaries, script.contextual_steps, script.phase_risks = result
        script.data_flow = summarize_data_flow(script)

    project.summary = summarize_project(project)

    count = sum(1 for s in project.scripts if s.summary) + (1 if project.summary else 0)
    phases = sum(1 for s in project.scripts if s.phase_summaries)
    print(f"[visualpy] Generated {count} summaries, {phases} phase descriptions", file=sys.stderr)


def _run_analyze(args: argparse.Namespace) -> None:
    """Run the analysis pipeline and output JSON."""
    target = Path(args.path).resolve()

    if not target.exists():
        print(f"[visualpy] Error: path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)

    project = _build_project(target)

    if args.summarize:
        _summarize_project(project)

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


def _project_from_dict(data: dict) -> AnalyzedProject:
    """Reconstruct an AnalyzedProject from a dict (inverse of dataclasses.asdict)."""
    scripts = []
    for s in data.get("scripts", []):
        steps = [
            Step(
                line_number=st["line_number"],
                type=st["type"],
                description=st["description"],
                function_name=st.get("function_name"),
                service=Service(**st["service"]) if st.get("service") else None,
                inputs=st.get("inputs", []),
                outputs=st.get("outputs", []),
            )
            for st in s.get("steps", [])
        ]
        scripts.append(
            AnalyzedScript(
                path=s["path"],
                is_entry_point=s.get("is_entry_point", False),
                steps=steps,
                imports_internal=s.get("imports_internal", []),
                imports_external=s.get("imports_external", []),
                services=[Service(**svc) for svc in s.get("services", [])],
                secrets=s.get("secrets", []),
                triggers=[Trigger(**t) for t in s.get("triggers", [])],
                signature=s.get("signature"),
                summary=s.get("summary"),
                phase_summaries=s.get("phase_summaries"),
                contextual_steps={int(k): v for k, v in s["contextual_steps"].items()}
                    if s.get("contextual_steps") else None,
                phase_risks=s.get("phase_risks"),
                data_flow=s.get("data_flow"),
            )
        )
    return AnalyzedProject(
        path=data["path"],
        scripts=scripts,
        connections=[ScriptConnection(**c) for c in data.get("connections", [])],
        services=[Service(**svc) for svc in data.get("services", [])],
        secrets=data.get("secrets", []),
        entry_points=data.get("entry_points", []),
        summary=data.get("summary"),
    )


def _run_serve(args: argparse.Namespace) -> None:
    """Analyze the target and start the web UI."""
    import uvicorn

    from visualpy.server import create_app

    if args.from_json:
        if args.path:
            print(
                f"[visualpy] Warning: --from-json takes precedence; ignoring path '{args.path}'",
                file=sys.stderr,
            )
        json_path = Path(args.from_json)
        if not json_path.exists():
            print(f"[visualpy] Error: JSON file not found: {args.from_json}", file=sys.stderr)
            sys.exit(1)
        try:
            data = json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[visualpy] Error: could not read JSON file: {exc}", file=sys.stderr)
            sys.exit(1)
        try:
            project = _project_from_dict(data)
        except (KeyError, TypeError, AttributeError, ValueError) as exc:
            print(
                f"[visualpy] Error: invalid JSON structure: {exc}\n"
                f"[visualpy] Hint: use 'visualpy analyze ... -o file.json' to generate a valid file",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"[visualpy] Loaded analysis from {args.from_json}", file=sys.stderr)
        if args.summarize:
            print(
                "[visualpy] Warning: --summarize ignored with --from-json "
                "(generate summaries during 'analyze' instead)",
                file=sys.stderr,
            )
    elif args.path:
        target = Path(args.path).resolve()
        if not target.exists():
            print(f"[visualpy] Error: path does not exist: {args.path}", file=sys.stderr)
            sys.exit(1)
        print(f"[visualpy] Analyzing {target}...", file=sys.stderr)
        project = _build_project(target)
        if args.summarize:
            _summarize_project(project)
    else:
        print("[visualpy] Error: either path or --from-json is required", file=sys.stderr)
        sys.exit(1)

    print(
        f"[visualpy] Found {len(project.scripts)} scripts, "
        f"{len(project.connections)} connections",
        file=sys.stderr,
    )

    app = create_app(project)
    print(f"[visualpy] Serving at http://{args.host}:{args.port}", file=sys.stderr)
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    except OSError as exc:
        print(
            f"[visualpy] Error: could not start server on {args.host}:{args.port}: {exc}\n"
            f"[visualpy] Hint: try a different port with --port",
            file=sys.stderr,
        )
        sys.exit(1)
