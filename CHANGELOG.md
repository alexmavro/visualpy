# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Compact mode for script flow diagrams — functions with >8 steps collapse to summary nodes
- Compact/Detailed toggle button on script pages (auto-shown for scripts with >30 steps)
- Importance scoring for scripts — overview sorted by connectivity, entry points, services
- "Key" badge on top scripts in overview
- LLM-generated plain-English summaries via litellm (BYOK — bring your own key)
- `--summarize` CLI flag for `analyze` and `serve` commands
- Per-script summaries from structured AST data (steps, services, triggers)
- Per-project executive summary from script summaries and connections
- Model override via `VISUALPY_MODEL` environment variable (default: `gemini/gemini-2.5-flash`)
- Summary rendering in web UI: overview header, script cards, script headers
- Graceful degradation when litellm not installed or API key missing
- README with badges, personas, quick start, roadmap, and acknowledgments
- CONTRIBUTING.md with non-dev-friendly contribution guide
- CODE_OF_CONDUCT.md (Contributor Covenant v2.1)
- SECURITY.md with responsible disclosure policy
- GitHub issue templates (bug report, feature request, question)
- Pull request template
- GitHub Actions CI pipeline (tests on push and PR)
- CHANGELOG.md (this file, retroactive)

## [0.1.0] - 2026-04-01

### Added

- **Web UI** — `visualpy serve /path` opens browser-based visualization
- Mermaid.js project dependency graph (left-to-right, scripts as nodes)
- Mermaid.js per-script flow diagrams (top-to-bottom, steps grouped by function)
- 6 step type shapes with colors: API call, file I/O, database, decision, output, transform
- Entry point highlighting in project graph
- Click-to-navigate: script node to flow view, step to detail panel
- Dark mode with Tailwind CSS and Alpine.js, persisted in localStorage
- HTMX step detail panel with inputs, outputs, and line numbers
- FastAPI server with app factory pattern and pre-computed project graph
- Script cards with service badges, step counts, entry point indicators
- Services and secrets inventory panels
- Global exception handler with graceful fallback
- Transform detection: comprehensions, 16 builtin transforms, string methods
- Inputs/outputs enrichment from assignments, open() modes, decision conditions
- File I/O false positive fix (serialization methods guarded by module)
- Cross-file structured detection using step inputs/outputs
- Analysis engine: `visualpy analyze /path` outputs structured JSON
- AST-based step detection for 6 step types
- Service mapping for 45+ Python libraries
- Cross-script connection resolution (imports, shared files, common services)
- Trigger detection (cron, webhook, CLI, import)
- Function signature parsing for main() type hints
- CLI with `analyze` and `serve` commands
- 140 tests with ~2.4s runtime
- Repo skeleton with models, fixtures, and dependency configuration

<!-- Links will be added when the first release is tagged -->
<!-- [Unreleased]: https://github.com/Lexi-Energy/visualpy/compare/v0.1.0...HEAD -->
<!-- [0.1.0]: https://github.com/Lexi-Energy/visualpy/releases/tag/v0.1.0 -->
