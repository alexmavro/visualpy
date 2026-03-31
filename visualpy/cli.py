"""CLI commands for visualpy."""

import argparse
import sys


def app():
    parser = argparse.ArgumentParser(
        prog="visualpy",
        description="Auto-visualise Python automations for non-technical stakeholders.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")

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
        print(f"[visualpy] analyze is not yet implemented. Target: {args.path}")
        sys.exit(0)

    if args.command == "serve":
        print(f"[visualpy] serve is not yet implemented. Target: {args.path}")
        sys.exit(0)
