"""Tests for LLM summarizer."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from visualpy.models import (
    AnalyzedProject,
    AnalyzedScript,
    ScriptConnection,
    Service,
    Step,
    Trigger,
)
from visualpy.summarizer.llm import (
    _build_project_prompt,
    _build_script_prompt,
    summarize_project,
    summarize_script,
)


# --- Fixtures ---


@pytest.fixture
def sample_script():
    return AnalyzedScript(
        path="fetch_data.py",
        is_entry_point=True,
        steps=[
            Step(
                line_number=10,
                type="api_call",
                description="requests.get(url)",
                function_name="fetch",
            ),
            Step(
                line_number=15,
                type="file_io",
                description="json.dump(data, f)",
                function_name="save",
            ),
            Step(
                line_number=20,
                type="decision",
                description="if verbose",
                function_name="main",
            ),
            Step(
                line_number=22,
                type="output",
                description="print(result)",
                function_name="main",
            ),
        ],
        services=[Service(name="HTTP Client", library="requests")],
        secrets=["API_KEY"],
        triggers=[Trigger(type="cli", detail="__main__ guard")],
    )


@pytest.fixture
def sample_project(sample_script):
    sample_script.summary = "Fetches data from an API and saves it locally."
    return AnalyzedProject(
        path="/tmp/test",
        scripts=[sample_script],
        connections=[
            ScriptConnection(
                source="fetch_data.py",
                target="upload.py",
                type="file_io",
                detail="fetch_data.py writes data.json -> upload.py reads data.json",
            )
        ],
        entry_points=["fetch_data.py"],
        services=[Service(name="HTTP Client", library="requests")],
        secrets=["API_KEY"],
    )


# --- Prompt building (deterministic, no LLM) ---


class TestBuildScriptPrompt:
    def test_returns_two_messages(self, sample_script):
        messages = _build_script_prompt(sample_script)
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_includes_script_path(self, sample_script):
        messages = _build_script_prompt(sample_script)
        assert "fetch_data.py" in messages[1]["content"]

    def test_includes_services(self, sample_script):
        messages = _build_script_prompt(sample_script)
        assert "HTTP Client" in messages[1]["content"]

    def test_includes_steps(self, sample_script):
        messages = _build_script_prompt(sample_script)
        content = messages[1]["content"]
        assert "requests.get(url)" in content
        assert "json.dump(data, f)" in content

    def test_includes_secrets(self, sample_script):
        messages = _build_script_prompt(sample_script)
        assert "API_KEY" in messages[1]["content"]

    def test_includes_triggers(self, sample_script):
        messages = _build_script_prompt(sample_script)
        assert "cli" in messages[1]["content"]

    def test_groups_steps_by_function(self, sample_script):
        messages = _build_script_prompt(sample_script)
        content = messages[1]["content"]
        assert "In fetch:" in content
        assert "In save:" in content
        assert "In main:" in content

    def test_empty_script(self):
        script = AnalyzedScript(path="empty.py")
        messages = _build_script_prompt(script)
        assert len(messages) == 2
        assert "empty.py" in messages[1]["content"]
        assert "No steps detected" in messages[1]["content"]

    def test_system_prompt_targets_non_technical(self, sample_script):
        messages = _build_script_prompt(sample_script)
        system = messages[0]["content"].lower()
        assert "non-technical" in system or "business" in system


class TestBuildProjectPrompt:
    def test_returns_two_messages(self, sample_project):
        messages = _build_project_prompt(sample_project)
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_includes_script_summaries(self, sample_project):
        messages = _build_project_prompt(sample_project)
        assert "Fetches data from an API" in messages[1]["content"]

    def test_includes_project_path(self, sample_project):
        messages = _build_project_prompt(sample_project)
        assert "/tmp/test" in messages[1]["content"]

    def test_includes_connections(self, sample_project):
        messages = _build_project_prompt(sample_project)
        assert "data.json" in messages[1]["content"]

    def test_includes_services(self, sample_project):
        messages = _build_project_prompt(sample_project)
        assert "HTTP Client" in messages[1]["content"]

    def test_script_without_summary(self):
        project = AnalyzedProject(
            path="/tmp/bare",
            scripts=[AnalyzedScript(path="bare.py")],
        )
        messages = _build_project_prompt(project)
        assert "No summary available" in messages[1]["content"]


# --- Graceful degradation ---


class TestGracefulDegradation:
    @patch("visualpy.summarizer.llm._call_llm", return_value=None)
    def test_script_returns_none_on_failure(self, mock_llm, sample_script):
        result = summarize_script(sample_script)
        assert result is None

    @patch("visualpy.summarizer.llm._call_llm", return_value=None)
    def test_project_returns_none_on_failure(self, mock_llm, sample_project):
        result = summarize_project(sample_project)
        assert result is None

    @patch("visualpy.summarizer.llm._call_llm", return_value="A helpful summary.")
    def test_script_returns_string_on_success(self, mock_llm, sample_script):
        result = summarize_script(sample_script)
        assert result == "A helpful summary."
        mock_llm.assert_called_once()

    @patch("visualpy.summarizer.llm._call_llm", return_value="A helpful summary.")
    def test_project_returns_string_on_success(self, mock_llm, sample_project):
        result = summarize_project(sample_project)
        assert result == "A helpful summary."
        mock_llm.assert_called_once()

    @patch("visualpy.summarizer.llm._call_llm")
    def test_model_env_var_override(self, mock_llm, sample_script):
        mock_llm.return_value = "summary"
        with patch.dict("os.environ", {"VISUALPY_MODEL": "openai/gpt-4o-mini"}):
            summarize_script(sample_script)
        assert mock_llm.call_args[0][1] == "openai/gpt-4o-mini"

    @patch("visualpy.summarizer.llm._call_llm")
    def test_explicit_model_parameter(self, mock_llm, sample_script):
        mock_llm.return_value = "summary"
        summarize_script(sample_script, model="openai/gpt-4o-mini")
        assert mock_llm.call_args[0][1] == "openai/gpt-4o-mini"

    @patch("visualpy.summarizer.llm._call_llm")
    def test_default_model(self, mock_llm, sample_script):
        mock_llm.return_value = "summary"
        with patch.dict("os.environ", {}, clear=True):
            summarize_script(sample_script)
        assert "gemini" in mock_llm.call_args[0][1]


class TestCallLlm:
    @patch.dict("sys.modules", {"litellm": None})
    def test_missing_litellm_returns_none(self):
        # Force ImportError by removing litellm from modules
        from visualpy.summarizer.llm import _call_llm

        with patch("builtins.__import__", side_effect=ImportError("no litellm")):
            result = _call_llm([{"role": "user", "content": "test"}], "test/model")
        assert result is None

    def test_llm_exception_returns_none(self):
        from visualpy.summarizer.llm import _call_llm

        mock_litellm = MagicMock()
        mock_litellm.completion.side_effect = RuntimeError("API error")

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            result = _call_llm(
                [{"role": "user", "content": "test"}], "test/model"
            )
        assert result is None

    def test_none_content_returns_none(self):
        from visualpy.summarizer.llm import _call_llm

        mock_response = MagicMock()
        mock_response.choices[0].message.content = None
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = mock_response

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            result = _call_llm(
                [{"role": "user", "content": "test"}], "test/model"
            )
        assert result is None

    def test_empty_content_returns_none(self):
        from visualpy.summarizer.llm import _call_llm

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "   "
        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = mock_response

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            result = _call_llm(
                [{"role": "user", "content": "test"}], "test/model"
            )
        assert result is None

    def test_successful_call(self):
        from visualpy.summarizer.llm import _call_llm

        mock_response = MagicMock()
        mock_response.choices[0].message.content = "  A summary.  "

        mock_litellm = MagicMock()
        mock_litellm.completion.return_value = mock_response

        with patch.dict("sys.modules", {"litellm": mock_litellm}):
            result = _call_llm(
                [{"role": "user", "content": "test"}], "test/model"
            )
        assert result == "A summary."
        mock_litellm.completion.assert_called_once_with(
            model="test/model",
            messages=[{"role": "user", "content": "test"}],
            max_tokens=2048,
        )


# --- Integration with real LLM (marked slow) ---


@pytest.mark.slow
class TestRealLLM:
    def test_summarize_script(self, hello_script, fixtures_dir):
        from visualpy.analyzer.ast_parser import analyze_file

        script = analyze_file(hello_script, fixtures_dir)
        result = summarize_script(script)
        assert result is not None
        assert len(result) > 10
        assert len(result) < 500

    def test_summarize_project(self, fixtures_dir):
        from visualpy.analyzer.cross_file import resolve_connections
        from visualpy.analyzer.scanner import scan_project

        agentic = fixtures_dir / "agentic_workflows"
        scripts = scan_project(agentic)
        connections = resolve_connections(scripts, agentic)

        for script in scripts:
            script.summary = summarize_script(script)

        project = AnalyzedProject(
            path=str(agentic),
            scripts=scripts,
            connections=connections,
            entry_points=[s.path for s in scripts if s.is_entry_point],
            services=[svc for s in scripts for svc in s.services],
            secrets=sorted({sec for s in scripts for sec in s.secrets}),
        )

        result = summarize_project(project)
        assert result is not None
        assert len(result) > 20
