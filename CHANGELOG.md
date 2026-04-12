# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Anti-pattern detection — deterministic code quality analysis: print spam, phase imbalance, error handling bulk, missing error handling, heavy transforms
- Health scoring — script cards show colored health badges (clean/minor issues/has issues/needs attention)
- Context-aware critiques — `explain_pattern()` shifts from praise to critique at high pattern counts
- Anti-pattern callout cards on script pages with severity-colored icons (red/amber/blue)
- Phase proportion percentage on accordion headers when >40% of total steps
- Credential deduplication in overview business view
- Condition simplification — business view cleans dict access and .get() patterns from if-conditions
- Pattern insights — deterministic teaching explanations for dedup groups (e.g., "Status logging — tracks workflow progress across 20 checkpoints")
- Risk annotations — per-phase "what could go wrong?" warnings piggybacked on existing LLM calls (zero extra cost)
- Data flow narrative — LLM-generated "data journey" callout (e.g., "Reads from Google Sheets → enriches via API → updates sheet")
- `explain_pattern()` in translate.py — keyword-matched insights for all dedup patterns with exception-safe fallback
- `summarize_data_flow()` in summarizer — 1 LLM call per script for data journey narrative
- Per-phase LLM summaries — contextual 1-2 sentence descriptions for each business phase (Setup, Processing, Storage, etc.)
- Contextual step descriptions — LLM-generated unique descriptions replacing generic "Handles potential errors" x9
- Step deduplication — identical business descriptions collapsed into expandable "Description (N locations)" groups
- `summarize_phases()` in summarizer — one LLM call per phase, JSON structured output, robust parser
- Phase summaries shown in accordion headers with blue left-border styling
- Step detail panel shows contextual description when available (falls back to deterministic translation)
- `--from-json` roundtrip preserves new phase_summaries and contextual_steps fields
- Business/Technical view toggle — switch between plain-English and developer views (persisted in localStorage)
- `translate.py` module — deterministic business-language translations for step descriptions, triggers, secrets, connection types
- Business-mode Mermaid diagrams — 4 pre-rendered flow variants (detailed/compact × tech/business)
- Translated UI labels: "External Service" not "API Call", "Runs daily at midnight" not "0 0 * * *", "AWS credentials" not "AWS_SECRET_ACCESS_KEY"
- Jinja2 template globals for translation functions — eliminates duplicated label dicts
- Per-step error isolation in business mode — one bad translation doesn't kill the whole diagram
- Phase inference — steps grouped by business intent (Setup, Processing, Storage, Error Handling, Reporting) instead of function names
- Pedagogical diagram — simple 3-5 phase pipeline replaces 50-node flowcharts in business view
- Progressive disclosure — business view shows summary first, phase accordions, then collapsed technical diagram
- Layout restructure — business view is a completely different layout (no sidebar, no grid, narrative-first)
- `--from-json` flag for `serve` command — load pre-computed analysis from JSON file
- Dockerfile + docker-compose for public demo deployment (pre-baked LLM summaries)
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
<!-- [Unreleased]: https://github.com/alexmavro/visualpy/compare/v0.1.0...HEAD -->
<!-- [0.1.0]: https://github.com/alexmavro/visualpy/releases/tag/v0.1.0 -->
