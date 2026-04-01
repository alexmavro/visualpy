# visualpy

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://github.com/Lexi-Energy/visualpy/actions/workflows/ci.yml/badge.svg)](https://github.com/Lexi-Energy/visualpy/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)

Auto-visualise Python automations for non-technical stakeholders.

Drop a folder of Python scripts, get a visual breakdown of what they do, how they connect, and what they need. No execution required, no config needed.

## Who is this for?

- **Operations teams** who inherited a folder of automation scripts and need to understand what each one does before touching anything.
- **Managers and team leads** who need to explain technical systems to stakeholders, clients, or auditors without reading code line by line.
- **Developers onboarding to a new codebase** who want a visual map of the project before diving into the source.

## Quick start

```bash
git clone https://github.com/Lexi-Energy/visualpy.git
cd visualpy
pip install -e .

visualpy analyze /path/to/your/scripts      # JSON breakdown
visualpy serve /path/to/your/scripts         # starts a local web UI
```

Requires Python 3.12 or later. No config files, no decorators in your code, no setup. Point it at a folder and go.

## How it works

visualpy reads your Python files using static analysis (the `ast` module). It never executes your code. It walks through the abstract syntax tree of each file and identifies:

- **What each script does** — API calls, file reads/writes, database operations, data transforms, decisions, and outputs
- **What services it talks to** — 45+ libraries mapped to human-readable service names (e.g., `import requests` = "HTTP", `import boto3` = "AWS S3")
- **How scripts connect** — shared file paths, cross-imports, common services
- **What secrets it needs** — environment variables, API keys, config lookups

The result is a structured project map, viewable as JSON or as an interactive web UI with dependency graphs and per-script flow diagrams.

## Features

- **Project dependency graph** — see how scripts relate to each other at a glance
- **Per-script flow diagrams** — step-by-step visual breakdown of what each file does, grouped by function
- **Service and secret detection** — instantly see which external services and API keys are in play
- **Entry point detection** — identifies scripts with `if __name__ == "__main__"`, cron triggers, webhooks, and CLI entry points
- **Dark mode** — toggle between light and dark themes, persisted across sessions
- **Click-to-explore** — click a script in the project graph to see its flow; click a step to see details
- **Zero config** — no decorators, no config files, no changes to your code
- **Fast** — static analysis, no execution, typical projects analyzed in under 2 seconds

## Roadmap

| Sprint | Status | What |
|--------|--------|------|
| 0: Init | Done | Repo skeleton, models, CLI stubs, test fixtures |
| 1: The Engine | Done | Folder-to-JSON analysis pipeline, 59 tests |
| 1.5: Hardening | Done | Transform detection, inputs/outputs enrichment, false positive fixes |
| 2: The Face | Done | Web UI with Mermaid.js graphs, dark mode, HTMX interactivity, 140 tests |
| 3: The Community | Done | FOSS prep, docs, issue templates, CI |
| 4: The Voice | Planned | LLM summaries (litellm, BYOK), per-script descriptions, project executive summary |
| 5: The Feedback Loop | Planned | Annotations, human-in-the-loop corrections |

## Contributing

We'd love your help — whether it's a bug report, a feature idea, or a question. You don't need to be a developer to contribute.

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to get started. We've written it specifically for people who might be new to open source.

## Acknowledgments

visualpy stands on the shoulders of great open-source projects. We studied their patterns and approaches:

- [pyflowchart](https://github.com/cdfmlr/pyflowchart) (MIT) — function subgraph grouping, AST-to-flowchart patterns
- [code2flow](https://github.com/scottrogowski/code2flow) (MIT) — entry point classification, directory hierarchy, graph organization
- [emerge](https://github.com/glato/emerge) (MIT) — dark mode toggle, data embedding strategy, module separation
- [staticfg](https://github.com/coetaur0/staticfg) (Apache-2.0) — AST visitor pattern for control flow
- [VizTracer](https://github.com/gaogaotiantian/viztracer) (Apache-2.0) — zero-config philosophy (no decorators, no code changes)

## License

[MIT](LICENSE)
