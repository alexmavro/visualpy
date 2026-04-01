# Contributing to visualpy

Whether you're a developer, a manager, or someone who just started using GitHub last week — you're welcome here. Every contribution matters, even a typo fix (although pls don't overdue it with issue reports and PRs on small stuff, combine them and be reasonable, I am but one person and have a job xD).

Not sure where to start? Read on. We've written this guide for people who might be new to open source.

## I found something broken

That's genuinely helpful — you're making the tool better for everyone.

1. Go to [Issues](https://github.com/Lexi-Energy/visualpy/issues/new/choose)
2. Pick **"Something isn't working"**
3. Fill in what happened and what you expected — that's all we need

You'll get a response within a few days. We might ask follow-up questions to understand the problem better.

## I have an idea

We love hearing ideas — technical or not. If you can describe what you'd like, that's enough.

1. Go to [Issues](https://github.com/Lexi-Energy/visualpy/issues/new/choose)
2. Pick **"I have an idea"**
3. Describe what you'd like and why it would be useful

Ideas don't need to be fully formed. "It would be cool if..." is a perfectly valid starting point.

## I have a question

There are no stupid questions. If something confused you, it probably means our documentation needs work — and that's on us, not you.

1. Go to [Issues](https://github.com/Lexi-Energy/visualpy/issues/new/choose)
2. Pick **"Question"**
3. Ask away

## I want to help with code

Great! Here's how to get set up.

### 1. Fork and clone

Click the **Fork** button at the top right of the [repository page](https://github.com/Lexi-Energy/visualpy). Then:

```bash
git clone https://github.com/YOUR-USERNAME/visualpy.git
cd visualpy
```

### 2. Set up the development environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Run the tests

```bash
pytest -m "not slow"
```

You should see the full test suite pass in a few seconds. If something fails, [open an issue](https://github.com/Lexi-Energy/visualpy/issues/new/choose) — it might be a setup problem on our end.

### 4. Make your changes

Create a branch for your work:

```bash
git checkout -b my-change
```

Make your edits. When you're done, run the tests again to make sure everything still passes.

### 5. Submit a pull request

```bash
git add <your-changed-files>
git commit -m "short description of what you changed"
git push origin my-change
```

Then go to your fork on GitHub. You'll see a banner offering to create a pull request. Click it, fill in the template, and submit.

That's it. We'll review your PR and get back to you.

## Project structure

A quick orientation:

```
visualpy/
  analyzer/      Analysis engine (AST parsing, service detection, etc.)
  templates/     Jinja2 HTML templates for the web UI
  mermaid.py     Mermaid.js graph generation
  server.py      FastAPI web server
  cli.py         Command-line interface
  models.py      Data models
tests/           Test suite (140+ tests)
static/          CSS and assets
```

## What we look for in pull requests

- **Tests pass** — run `pytest -m "not slow"` before submitting
- **Focused changes** — one thing per PR is easier to review than five things at once
- **Clean code** — readable, no debug prints left in, no commented-out code

We don't enforce a specific commit message format or coding style. Just keep it readable.

## Code of conduct

We follow the [Contributor Covenant](CODE_OF_CONDUCT.md). In short: be kind, be respectful, assume good intentions.

## Thank you

Seriously, whether you reported a bug, suggested a feature, asked a question, or submitted code — you made this project better. Thank you.
