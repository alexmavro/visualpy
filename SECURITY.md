# Security Policy

## How visualpy works

visualpy performs **static analysis only**. It reads Python files using the `ast` module and never executes any code. The analysis pipeline has no network access, no eval/exec calls, and no dynamic imports.

The web UI (`visualpy serve`) runs a local FastAPI server. By default it binds to `127.0.0.1` (localhost only) and is not exposed to the network.

## Threat surface

- **AST parsing** — Python's `ast.parse()` is safe for untrusted input. It parses syntax without executing code.
- **Web UI** — local-only by default (`127.0.0.1`). If you override this with `--host 0.0.0.0`, the UI becomes network-accessible and is unauthenticated. Don't expose it to the public internet.
- **No secrets in output** — visualpy detects environment variable lookups (e.g., `os.getenv("API_KEY")`) but never reads their values.

## Reporting a vulnerability

If you find a security issue, please report it responsibly:

1. **Open a private security advisory** on GitHub: [New Security Advisory](https://github.com/alexmavro/visualpy/security/advisories/new)
2. Or email the maintainer directly (see GitHub profile for contact info)

Please do not open a public issue for security vulnerabilities.

We will acknowledge reports within 48 hours and aim to provide a fix or mitigation within 7 days for confirmed issues.

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |
