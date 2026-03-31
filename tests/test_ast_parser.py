"""Tests for ast_parser module."""

from pathlib import Path

from visualpy.analyzer.ast_parser import analyze_file


def test_hello_fixture(hello_script, fixtures_dir):
    result = analyze_file(hello_script, fixtures_dir)

    # Path is relative to project root
    assert result.path == "hello.py"

    # Entry point detected
    assert result.is_entry_point is True

    # Secrets: MY_API_KEY
    assert "MY_API_KEY" in result.secrets

    # Services: requests → HTTP Client
    assert any(s.name == "HTTP Client" for s in result.services)

    # External imports include requests, os, json
    assert "requests" in result.imports_external
    assert "os" in result.imports_external
    assert "json" in result.imports_external

    # No internal imports in hello.py
    assert result.imports_internal == []

    # Triggers: __main__ guard
    assert any(t.type == "cli" and t.detail == "__main__ guard" for t in result.triggers)

    # Signature: main(url, output, verbose)
    assert result.signature is not None
    assert "url" in result.signature
    assert "output" in result.signature
    assert "verbose" in result.signature


def test_hello_steps(hello_script, fixtures_dir):
    result = analyze_file(hello_script, fixtures_dir)
    step_types = {s.type for s in result.steps}

    # Must have api_call (requests.get), file_io (open + json.dump), decision (if verbose), output (print)
    assert "api_call" in step_types
    assert "file_io" in step_types
    assert "decision" in step_types
    assert "output" in step_types

    # Check function scope tracking
    api_steps = [s for s in result.steps if s.type == "api_call"]
    assert any(s.function_name == "fetch_data" for s in api_steps)

    file_steps = [s for s in result.steps if s.type == "file_io"]
    assert any(s.function_name == "save_results" for s in file_steps)


def test_steps_ordered_by_line(hello_script, fixtures_dir):
    result = analyze_file(hello_script, fixtures_dir)
    lines = [s.line_number for s in result.steps]
    assert lines == sorted(lines)


def test_syntax_error_returns_empty(fixtures_dir, tmp_path):
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def oops(:\n  pass")
    result = analyze_file(bad_file, tmp_path)
    assert result.path == "bad.py"
    assert result.steps == []
    assert result.services == []


def test_no_main_no_entry_point(tmp_path):
    script = tmp_path / "helper.py"
    script.write_text("def helper(): return 42\n")
    result = analyze_file(script, tmp_path)
    assert result.is_entry_point is False
    assert result.signature is None


def test_db_operations(tmp_path):
    script = tmp_path / "db.py"
    script.write_text("""
import sqlite3
conn = sqlite3.connect("test.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM users")
rows = cursor.fetchall()
conn.commit()
""")
    result = analyze_file(script, tmp_path)
    db_steps = [s for s in result.steps if s.type == "db_op"]
    assert len(db_steps) >= 2  # execute + fetchall at minimum


def test_db_op_no_false_positives(tmp_path):
    """Common methods like .add(), .find(), .flush() on non-DB objects must NOT be db_op."""
    script = tmp_path / "nodb.py"
    script.write_text("""
items = set()
items.add("hello")
idx = "abcdef".find("c")
import sys
sys.stdout.flush()
""")
    result = analyze_file(script, tmp_path)
    db_steps = [s for s in result.steps if s.type == "db_op"]
    assert db_steps == [], f"False positive db_op steps: {db_steps}"


def test_logging_output(tmp_path):
    script = tmp_path / "loggy.py"
    script.write_text("""
import logging
logger = logging.getLogger(__name__)
logger.info("starting")
logger.error("something broke")
""")
    result = analyze_file(script, tmp_path)
    output_steps = [s for s in result.steps if s.type == "output"]
    assert len(output_steps) >= 2


def test_internal_import_detection(tmp_path):
    (tmp_path / "utils.py").write_text("def helper(): pass\n")
    script = tmp_path / "main.py"
    script.write_text("from utils import helper\nhelper()\n")
    result = analyze_file(script, tmp_path)
    assert "utils" in result.imports_internal


def test_multiple_secrets(tmp_path):
    script = tmp_path / "secrets.py"
    script.write_text("""
import os
key = os.getenv("API_KEY")
secret = os.environ.get("SECRET")
token = os.environ["TOKEN"]
""")
    result = analyze_file(script, tmp_path)
    assert set(result.secrets) == {"API_KEY", "SECRET", "TOKEN"}
