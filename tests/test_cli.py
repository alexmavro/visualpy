"""Tests for CLI integration."""

import json
import subprocess
import sys


def test_analyze_hello(hello_script):
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "analyze", str(hello_script)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)

    assert "scripts" in data
    assert len(data["scripts"]) == 1
    assert data["scripts"][0]["path"] == "hello.py"
    assert data["scripts"][0]["is_entry_point"] is True
    assert len(data["scripts"][0]["secrets"]) > 0
    assert len(data["scripts"][0]["services"]) > 0


def test_analyze_folder(fixtures_dir):
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "analyze", str(fixtures_dir / "agentic_workflows")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)

    assert len(data["scripts"]) == 8
    assert len(data["services"]) > 0
    assert len(data["entry_points"]) > 0


def test_analyze_output_file(hello_script, tmp_path):
    out_file = tmp_path / "result.json"
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "analyze", str(hello_script), "-o", str(out_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert data["scripts"][0]["path"] == "hello.py"


def test_analyze_nonexistent_path():
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "analyze", "/does/not/exist"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "Error" in result.stderr


def test_analyze_summarize_flag(hello_script):
    """--summarize flag is accepted and summary fields are present in output."""
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "analyze", str(hello_script), "--summarize"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "summary" in data
    assert "summary" in data["scripts"][0]


def test_version():
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.1.0" in result.stdout
