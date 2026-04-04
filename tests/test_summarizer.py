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
    _build_data_flow_prompt,
    _build_phase_prompt,
    _build_project_prompt,
    _build_script_prompt,
    _parse_phase_response,
    summarize_data_flow,
    summarize_phases,
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


# --- Phase prompt building (Sprint 7) ---


class TestBuildPhasePrompt:
    def test_returns_two_messages(self, sample_script):
        steps = sample_script.steps[:2]
        messages = _build_phase_prompt(sample_script, "Setup & Data Gathering", steps)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_includes_phase_name(self, sample_script):
        steps = sample_script.steps[:2]
        messages = _build_phase_prompt(sample_script, "Setup & Data Gathering", steps)
        assert "Setup & Data Gathering" in messages[1]["content"]

    def test_includes_step_line_numbers(self, sample_script):
        steps = sample_script.steps[:2]
        messages = _build_phase_prompt(sample_script, "Setup & Data Gathering", steps)
        content = messages[1]["content"]
        assert "Line 10" in content
        assert "Line 15" in content

    def test_includes_services(self, sample_script):
        steps = sample_script.steps[:1]
        messages = _build_phase_prompt(sample_script, "Setup", steps)
        assert "HTTP Client" in messages[1]["content"]

    def test_includes_step_descriptions(self, sample_script):
        steps = sample_script.steps[:1]
        messages = _build_phase_prompt(sample_script, "Setup", steps)
        assert "requests.get(url)" in messages[1]["content"]

    def test_requests_json_output(self, sample_script):
        steps = sample_script.steps[:1]
        messages = _build_phase_prompt(sample_script, "Setup", steps)
        content = messages[1]["content"]
        assert "phase_summary" in content
        assert "steps" in content

    def test_anti_generic_instructions(self, sample_script):
        steps = sample_script.steps[:1]
        messages = _build_phase_prompt(sample_script, "Setup", steps)
        content = messages[1]["content"]
        assert "Handles potential errors" in content  # anti-instruction
        assert "SPECIFIC service" in content

    def test_empty_steps_list(self, sample_script):
        messages = _build_phase_prompt(sample_script, "Setup", [])
        assert len(messages) == 2
        assert "No steps." in messages[1]["content"]


class TestParsePhaseResponse:
    def _steps(self, lines):
        return [Step(line_number=ln, type="api_call", description="x") for ln in lines]

    def test_valid_json(self):
        raw = '{"phase_summary": "Sets everything up.", "steps": {"10": "Connects to API", "20": "Loads config"}}'
        steps = self._steps([10, 20])
        summary, descs, risk = _parse_phase_response(raw, steps)
        assert summary == "Sets everything up."
        assert descs == {10: "Connects to API", 20: "Loads config"}

    def test_strips_markdown_fences(self):
        raw = '```json\n{"phase_summary": "OK", "steps": {"5": "desc"}}\n```'
        steps = self._steps([5])
        summary, descs, risk = _parse_phase_response(raw, steps)
        assert summary == "OK"
        assert descs == {5: "desc"}

    def test_strips_thinking_prefix(self):
        raw = 'Let me think about this...\n\n{"phase_summary": "Works", "steps": {"7": "action"}}'
        steps = self._steps([7])
        summary, descs, risk = _parse_phase_response(raw, steps)
        assert summary == "Works"
        assert descs == {7: "action"}

    def test_strips_trailing_text(self):
        raw = '{"phase_summary": "OK", "steps": {"5": "desc"}} Hope this helps!'
        steps = self._steps([5])
        summary, descs, risk = _parse_phase_response(raw, steps)
        assert summary == "OK"
        assert descs == {5: "desc"}

    def test_strips_both_prefix_and_trailing(self):
        raw = 'Here is the result:\n{"phase_summary": "OK", "steps": {}}\nLet me know if you need more.'
        summary, descs, risk = _parse_phase_response(raw, [])
        assert summary == "OK"

    def test_invalid_json_returns_none(self):
        raw = "this is not json at all"
        summary, descs, risk = _parse_phase_response(raw, [])
        assert summary is None
        assert descs == {}

    def test_missing_phase_summary(self):
        raw = '{"steps": {"10": "desc"}}'
        steps = self._steps([10])
        summary, descs, risk = _parse_phase_response(raw, steps)
        assert summary is None
        assert descs == {10: "desc"}

    def test_missing_steps_key(self):
        raw = '{"phase_summary": "Good summary"}'
        steps = self._steps([10])
        summary, descs, risk = _parse_phase_response(raw, steps)
        assert summary == "Good summary"
        assert descs == {}

    def test_unknown_line_numbers_filtered(self):
        raw = '{"phase_summary": "OK", "steps": {"10": "valid", "999": "invalid"}}'
        steps = self._steps([10])
        summary, descs, risk = _parse_phase_response(raw, steps)
        assert descs == {10: "valid"}

    def test_empty_summary_treated_as_none(self):
        raw = '{"phase_summary": "  ", "steps": {}}'
        summary, descs, risk = _parse_phase_response(raw, [])
        assert summary is None

    def test_no_brace_returns_none(self):
        raw = "no json here whatsoever"
        summary, descs, risk = _parse_phase_response(raw, [])
        assert summary is None
        assert descs == {}


class TestSummarizePhases:
    def _make_script(self):
        return AnalyzedScript(
            path="test.py",
            steps=[
                Step(line_number=1, type="api_call", description="requests.get()"),
                Step(line_number=2, type="transform", description=".strip()"),
                Step(line_number=3, type="decision", description="try/except err"),
            ],
        )

    @patch("visualpy.summarizer.llm._call_llm")
    def test_returns_tuple_on_success(self, mock_llm):
        mock_llm.return_value = '{"phase_summary": "Does stuff", "steps": {"1": "Gets data"}}'
        script = self._make_script()
        result = summarize_phases(script)
        assert result is not None
        summaries, steps, risks = result
        assert isinstance(summaries, dict)
        assert isinstance(steps, dict)
        assert isinstance(risks, dict)

    @patch("visualpy.summarizer.llm._call_llm", return_value=None)
    def test_returns_none_when_all_fail(self, mock_llm):
        script = self._make_script()
        result = summarize_phases(script)
        assert result is None

    @patch("visualpy.summarizer.llm._call_llm")
    def test_partial_success(self, mock_llm):
        """One phase succeeds, others fail → partial results."""
        def side_effect(messages, model):
            content = messages[1]["content"]
            if "Setup" in content:
                return '{"phase_summary": "Sets up", "steps": {"1": "Gets data"}}'
            return None
        mock_llm.side_effect = side_effect
        script = self._make_script()
        result = summarize_phases(script)
        assert result is not None
        summaries, steps, risks = result
        assert "setup" in summaries
        assert 1 in steps

    def test_empty_script_returns_none(self):
        script = AnalyzedScript(path="empty.py")
        result = summarize_phases(script)
        assert result is None

    @patch("visualpy.summarizer.llm._call_llm")
    def test_risks_collected(self, mock_llm):
        mock_llm.return_value = (
            '{"phase_summary": "Does stuff", "steps": {"1": "Gets data"}, '
            '"risk": "API might be rate-limited"}'
        )
        script = self._make_script()
        result = summarize_phases(script)
        assert result is not None
        _, _, risks = result
        assert isinstance(risks, dict)
        assert any("rate-limited" in v for v in risks.values())

    @patch("visualpy.summarizer.llm._call_llm")
    def test_partial_risks(self, mock_llm):
        """Some phases return risk, others don't → partial risks collected."""
        def side_effect(messages, model):
            content = messages[1]["content"]
            if "Setup" in content:
                return '{"phase_summary": "Sets up", "steps": {"1": "x"}, "risk": "Auth may expire"}'
            return '{"phase_summary": "Processes", "steps": {"2": "y"}}'
        mock_llm.side_effect = side_effect
        script = self._make_script()
        result = summarize_phases(script)
        assert result is not None
        _, _, risks = result
        assert "setup" in risks
        assert "processing" not in risks


class TestParsePhaseResponseRisk:
    """Tests for risk extraction in _parse_phase_response."""

    def _steps(self, lines):
        return [Step(line_number=ln, type="api_call", description="x") for ln in lines]

    def test_extracts_risk(self):
        raw = '{"phase_summary": "OK", "steps": {}, "risk": "API timeout possible"}'
        summary, descs, risk = _parse_phase_response(raw, [])
        assert risk == "API timeout possible"

    def test_empty_risk_is_none(self):
        raw = '{"phase_summary": "OK", "steps": {}, "risk": ""}'
        summary, descs, risk = _parse_phase_response(raw, [])
        assert risk is None

    def test_whitespace_risk_is_none(self):
        raw = '{"phase_summary": "OK", "steps": {}, "risk": "   "}'
        summary, descs, risk = _parse_phase_response(raw, [])
        assert risk is None

    def test_missing_risk_is_none(self):
        raw = '{"phase_summary": "OK", "steps": {}}'
        summary, descs, risk = _parse_phase_response(raw, [])
        assert risk is None

    def test_risk_stripped(self):
        raw = '{"phase_summary": "OK", "steps": {}, "risk": "  trimmed  "}'
        summary, descs, risk = _parse_phase_response(raw, [])
        assert risk == "trimmed"

    def test_risk_with_steps(self):
        raw = '{"phase_summary": "OK", "steps": {"10": "desc"}, "risk": "Rate limit"}'
        steps = self._steps([10])
        summary, descs, risk = _parse_phase_response(raw, steps)
        assert descs == {10: "desc"}
        assert risk == "Rate limit"


class TestBuildPhasePromptRisk:
    """Tests that _build_phase_prompt requests risk in the output."""

    def test_prompt_includes_risk_instruction(self, sample_script):
        steps = [Step(line_number=10, type="api_call", description="requests.get()")]
        messages = _build_phase_prompt(sample_script, "Setup", steps)
        user_msg = messages[1]["content"]
        assert "risk" in user_msg.lower()
        assert "failure mode" in user_msg.lower() or "what could go wrong" in user_msg.lower()

    def test_expected_json_includes_risk_field(self, sample_script):
        steps = [Step(line_number=10, type="api_call", description="requests.get()")]
        messages = _build_phase_prompt(sample_script, "Setup", steps)
        user_msg = messages[1]["content"]
        assert '"risk"' in user_msg


# --- Sprint 7.5: Data Flow Narrative ---


class TestBuildDataFlowPrompt:
    """Tests for _build_data_flow_prompt."""

    def test_returns_two_messages(self, sample_script):
        messages = _build_data_flow_prompt(sample_script)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"

    def test_includes_services(self):
        script = AnalyzedScript(
            path="test.py",
            steps=[Step(line_number=1, type="api_call", description="requests.get()")],
            services=[Service(name="Google Sheets", library="gspread")],
        )
        messages = _build_data_flow_prompt(script)
        assert "Google Sheets" in messages[1]["content"]

    def test_includes_arrow_instruction(self, sample_script):
        messages = _build_data_flow_prompt(sample_script)
        user_msg = messages[1]["content"]
        assert "\u2192" in user_msg

    def test_includes_phases(self, sample_script):
        messages = _build_data_flow_prompt(sample_script)
        user_msg = messages[1]["content"]
        assert "Phases:" in user_msg

    def test_includes_io_variables(self):
        script = AnalyzedScript(
            path="test.py",
            steps=[
                Step(
                    line_number=1, type="api_call", description="requests.get()",
                    inputs=["url", "headers"], outputs=["response"],
                ),
            ],
        )
        messages = _build_data_flow_prompt(script)
        user_msg = messages[1]["content"]
        assert "url" in user_msg
        assert "response" in user_msg


class TestSummarizeDataFlow:
    """Tests for summarize_data_flow."""

    def test_empty_script_returns_none(self):
        script = AnalyzedScript(path="empty.py")
        result = summarize_data_flow(script)
        assert result is None

    @patch("visualpy.summarizer.llm._call_llm", return_value="Reads data \u2192 transforms \u2192 uploads")
    def test_success(self, mock_llm):
        script = AnalyzedScript(
            path="test.py",
            steps=[Step(line_number=1, type="api_call", description="requests.get()")],
        )
        result = summarize_data_flow(script)
        assert result is not None
        assert "\u2192" in result

    @patch("visualpy.summarizer.llm._call_llm", return_value=None)
    def test_failure_returns_none(self, mock_llm):
        script = AnalyzedScript(
            path="test.py",
            steps=[Step(line_number=1, type="api_call", description="requests.get()")],
        )
        result = summarize_data_flow(script)
        assert result is None


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
