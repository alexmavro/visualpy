"""Tests for CLI integration."""

import dataclasses
import json
import subprocess
import sys

import pytest

from visualpy.cli import _project_from_dict
from visualpy.models import (
    AnalyzedProject,
    AnalyzedScript,
    ScriptConnection,
    Service,
    Step,
    Trigger,
)


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

    assert len(data["scripts"]) == 10
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


@pytest.mark.slow
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


# --- --from-json ---


def test_project_from_dict_roundtrip():
    """asdict → _project_from_dict should reconstruct equivalent project."""
    project = AnalyzedProject(
        path="/tmp/test",
        scripts=[
            AnalyzedScript(
                path="example.py",
                is_entry_point=True,
                steps=[
                    Step(
                        line_number=10,
                        type="api_call",
                        description="requests.get()",
                        function_name="fetch",
                        service=Service(name="HTTP", library="requests"),
                        inputs=["url"],
                        outputs=["response"],
                    ),
                ],
                services=[Service(name="HTTP", library="requests")],
                secrets=["API_KEY"],
                triggers=[Trigger(type="cli", detail="__main__")],
                signature={"url": "str"},
                summary="Fetches data.",
            ),
        ],
        connections=[
            ScriptConnection(source="a.py", target="b.py", type="import", detail="a→b"),
        ],
        services=[Service(name="HTTP", library="requests")],
        secrets=["API_KEY"],
        entry_points=["example.py"],
        summary="A test project.",
    )
    data = dataclasses.asdict(project)
    restored = _project_from_dict(data)

    assert restored.path == project.path
    assert restored.summary == project.summary
    assert len(restored.scripts) == 1
    assert restored.scripts[0].path == "example.py"
    assert restored.scripts[0].is_entry_point is True
    assert restored.scripts[0].steps[0].line_number == 10
    assert restored.scripts[0].steps[0].service.name == "HTTP"
    assert restored.scripts[0].steps[0].inputs == ["url"]
    assert restored.scripts[0].triggers[0].type == "cli"
    assert restored.scripts[0].summary == "Fetches data."
    assert len(restored.connections) == 1
    assert restored.connections[0].source == "a.py"
    assert restored.entry_points == ["example.py"]


def test_from_json_roundtrip_via_cli(hello_script, tmp_path):
    """analyze → JSON file → serve --from-json should accept the file."""
    json_file = tmp_path / "analysis.json"
    # Generate JSON
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "analyze", str(hello_script), "-o", str(json_file)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json_file.exists()

    # Load and verify it reconstructs
    data = json.loads(json_file.read_text())
    project = _project_from_dict(data)
    assert len(project.scripts) == 1
    assert project.scripts[0].path == "hello.py"


def test_from_json_missing_file():
    """--from-json with nonexistent file should fail cleanly."""
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "serve", "--from-json", "/does/not/exist.json"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Error" in result.stderr


def test_serve_requires_path_or_from_json():
    """serve with neither path nor --from-json should fail."""
    result = subprocess.run(
        [sys.executable, "-m", "visualpy", "serve"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Error" in result.stderr or "required" in result.stderr.lower()


# --- Sprint 7: phase_summaries + contextual_steps ---


def test_project_from_dict_with_phase_summaries():
    """phase_summaries should roundtrip through asdict → _project_from_dict."""
    project = AnalyzedProject(
        path="/tmp/test",
        scripts=[
            AnalyzedScript(
                path="x.py",
                steps=[Step(line_number=1, type="api_call", description="get()")],
                phase_summaries={"setup": "Loads the config."},
            ),
        ],
    )
    data = dataclasses.asdict(project)
    restored = _project_from_dict(data)
    assert restored.scripts[0].phase_summaries == {"setup": "Loads the config."}


def test_project_from_dict_with_contextual_steps():
    """contextual_steps int keys should survive JSON roundtrip."""
    project = AnalyzedProject(
        path="/tmp/test",
        scripts=[
            AnalyzedScript(
                path="x.py",
                steps=[Step(line_number=10, type="api_call", description="get()")],
                contextual_steps={10: "Fetches the price list from Shopify"},
            ),
        ],
    )
    data = dataclasses.asdict(project)
    # Simulate JSON roundtrip (int keys become strings).
    data = json.loads(json.dumps(data))
    restored = _project_from_dict(data)
    assert restored.scripts[0].contextual_steps == {10: "Fetches the price list from Shopify"}
    assert isinstance(list(restored.scripts[0].contextual_steps.keys())[0], int)


def test_project_from_dict_backward_compat():
    """Old JSON without phase_summaries/contextual_steps should load fine."""
    data = {
        "path": "/tmp/old",
        "scripts": [
            {
                "path": "old.py",
                "is_entry_point": False,
                "steps": [],
                "imports_internal": [],
                "imports_external": [],
                "services": [],
                "secrets": [],
                "triggers": [],
                "signature": None,
                "summary": None,
            }
        ],
        "connections": [],
        "services": [],
        "secrets": [],
        "entry_points": [],
        "summary": None,
    }
    restored = _project_from_dict(data)
    assert restored.scripts[0].phase_summaries is None
    assert restored.scripts[0].contextual_steps is None


def test_project_from_dict_contextual_steps_none():
    """Explicit null contextual_steps in JSON → None in model."""
    data = {
        "path": "/tmp",
        "scripts": [
            {
                "path": "n.py",
                "steps": [],
                "contextual_steps": None,
                "phase_summaries": None,
            }
        ],
        "connections": [],
    }
    restored = _project_from_dict(data)
    assert restored.scripts[0].contextual_steps is None
    assert restored.scripts[0].phase_summaries is None


# --- Sprint 7.5: phase_risks ---


def test_project_from_dict_with_phase_risks():
    """phase_risks should roundtrip through asdict → _project_from_dict."""
    project = AnalyzedProject(
        path="/test",
        scripts=[
            AnalyzedScript(
                path="test.py",
                phase_risks={"setup": "Auth token may have expired."},
            ),
        ],
    )
    data = dataclasses.asdict(project)
    restored = _project_from_dict(data)
    assert restored.scripts[0].phase_risks == {"setup": "Auth token may have expired."}


def test_project_from_dict_backward_compat_no_risks():
    """Old JSON without phase_risks should load fine (None)."""
    data = {
        "path": "/test",
        "scripts": [
            {
                "path": "test.py",
                "steps": [],
                "services": [],
                "triggers": [],
                "secrets": [],
                "imports_internal": [],
                "imports_external": [],
            },
        ],
        "connections": [],
    }
    restored = _project_from_dict(data)
    assert restored.scripts[0].phase_risks is None


# --- Sprint 7.5: data_flow ---


def test_project_from_dict_with_data_flow():
    """data_flow should roundtrip through asdict → _project_from_dict."""
    project = AnalyzedProject(
        path="/test",
        scripts=[
            AnalyzedScript(
                path="test.py",
                data_flow="Reads leads from Google Sheets \u2192 enriches via API \u2192 updates sheet",
            ),
        ],
    )
    data = dataclasses.asdict(project)
    restored = _project_from_dict(data)
    assert restored.scripts[0].data_flow == (
        "Reads leads from Google Sheets \u2192 enriches via API \u2192 updates sheet"
    )


def test_project_from_dict_backward_compat_no_data_flow():
    """Old JSON without data_flow should load fine (None)."""
    data = {
        "path": "/test",
        "scripts": [
            {
                "path": "test.py",
                "steps": [],
                "services": [],
                "triggers": [],
                "secrets": [],
                "imports_internal": [],
                "imports_external": [],
            },
        ],
        "connections": [],
    }
    restored = _project_from_dict(data)
    assert restored.scripts[0].data_flow is None
