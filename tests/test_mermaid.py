"""Tests for Mermaid syntax generation."""

from visualpy.analyzer.ast_parser import analyze_file
from visualpy.analyzer.cross_file import resolve_connections
from visualpy.analyzer.scanner import scan_project
from visualpy.mermaid import (
    _escape_label,
    _sanitize_id,
    _step_node,
    project_graph,
    script_flow,
)
from visualpy.models import (
    AnalyzedProject,
    AnalyzedScript,
    ScriptConnection,
    Service,
    Step,
)


# --- _sanitize_id ---


def test_sanitize_id_simple():
    assert _sanitize_id("hello") == "n_hello"


def test_sanitize_id_dots_and_slashes():
    assert _sanitize_id("scripts/hello.py") == "n_scripts_hello_py"


def test_sanitize_id_spaces():
    assert _sanitize_id("my script") == "n_my_script"


def test_sanitize_id_unicode():
    result = _sanitize_id("schön.py")
    assert result.startswith("n_")
    assert "." not in result


def test_sanitize_id_already_clean():
    assert _sanitize_id("hello_world") == "n_hello_world"


# --- _escape_label ---


def test_escape_label_quotes():
    assert "#quot;" in _escape_label('say "hello"')


def test_escape_label_angle_brackets():
    result = _escape_label("list<int>")
    assert "#lt;" in result
    assert "#gt;" in result


def test_escape_label_pipe():
    assert "#124;" in _escape_label("a|b")


def test_escape_label_braces():
    result = _escape_label("if {x}")
    assert "#lbrace;" in result
    assert "#rbrace;" in result


def test_escape_label_truncation():
    long_text = "a" * 100
    result = _escape_label(long_text, max_len=20)
    # Truncation happens before escaping; plain chars stay same length.
    assert len(result) == 20
    assert result.endswith("...")


def test_escape_label_truncation_before_escaping():
    """Special chars at the boundary should not produce split escape sequences."""
    text = "x" * 58 + '"q'  # 60 chars, quote at position 59
    result = _escape_label(text, max_len=60)
    # Truncated to 57 chars + "..." = 60 original, then " is escaped to #quot;
    # No split escape sequences should appear
    assert "#quo..." not in result


def test_escape_label_no_truncation_when_short():
    text = "short text"
    assert _escape_label(text) == text


def test_escape_label_hash():
    assert "#35;" in _escape_label("# comment")


# --- _step_node ---


def test_step_node_api_call():
    step = Step(line_number=10, type="api_call", description="requests.get()")
    result = _step_node(step, "hello")
    assert "n_hello_10" in result
    assert "API: requests.get()" in result
    assert '["' in result  # rectangle brackets
    assert ":::api" in result


def test_step_node_file_io():
    step = Step(line_number=15, type="file_io", description="open(data.csv)")
    result = _step_node(step, "hello")
    assert "[/" in result  # parallelogram
    assert ":::fileio" in result


def test_step_node_db_op():
    step = Step(line_number=18, type="db_op", description="cursor.execute()")
    result = _step_node(step, "hello")
    assert "[(" in result  # cylinder
    assert ":::dbop" in result


def test_step_node_decision():
    step = Step(line_number=20, type="decision", description="if verbose")
    result = _step_node(step, "hello")
    assert "{" in result  # diamond
    assert ":::decision" in result
    # Decision should NOT have a prefix
    assert "Decision:" not in result


def test_step_node_output():
    step = Step(line_number=22, type="output", description="print()")
    result = _step_node(step, "hello")
    assert "([" in result  # stadium
    assert ":::output" in result


def test_step_node_transform():
    step = Step(line_number=25, type="transform", description="sorted()")
    result = _step_node(step, "hello")
    assert "[[" in result  # subroutine
    assert ":::transform" in result


def test_step_node_unknown_type_fallback():
    step = Step(line_number=1, type="unknown", description="something")
    result = _step_node(step, "test")
    assert "n_test_1" in result
    assert "something" in result


# --- project_graph ---


def test_project_graph_single_script():
    script = AnalyzedScript(path="hello.py", is_entry_point=True)
    project = AnalyzedProject(
        path="/tmp/test",
        scripts=[script],
        entry_points=["hello.py"],
    )
    result = project_graph(project)
    assert "graph LR" in result
    assert "hello.py" in result
    assert ":::entry" in result
    assert "classDef entry" in result


def test_project_graph_connections():
    scripts = [
        AnalyzedScript(path="a.py"),
        AnalyzedScript(path="b.py"),
    ]
    connections = [
        ScriptConnection(source="a.py", target="b.py", type="import", detail="a imports b"),
    ]
    project = AnalyzedProject(
        path="/tmp", scripts=scripts, connections=connections
    )
    result = project_graph(project)
    assert "n_a_py" in result
    assert "n_b_py" in result
    assert "-->|" in result
    assert "import" in result


def test_project_graph_directory_subgraphs():
    scripts = [
        AnalyzedScript(path="src/a.py"),
        AnalyzedScript(path="lib/b.py"),
    ]
    project = AnalyzedProject(path="/tmp", scripts=scripts)
    result = project_graph(project)
    assert "subgraph" in result
    assert "src" in result
    assert "lib" in result


def test_project_graph_no_subgraph_for_flat_project():
    scripts = [
        AnalyzedScript(path="a.py"),
        AnalyzedScript(path="b.py"),
    ]
    project = AnalyzedProject(path="/tmp", scripts=scripts)
    result = project_graph(project)
    assert "subgraph" not in result


def test_project_graph_entry_point_styling():
    scripts = [
        AnalyzedScript(path="main.py", is_entry_point=True),
        AnalyzedScript(path="helper.py", is_entry_point=False),
    ]
    project = AnalyzedProject(
        path="/tmp", scripts=scripts, entry_points=["main.py"]
    )
    result = project_graph(project)
    # main.py should have entry class
    lines = result.split("\n")
    main_line = [l for l in lines if "main.py" in l and "n_main_py" in l][0]
    helper_line = [l for l in lines if "helper.py" in l and "n_helper_py" in l][0]
    assert ":::entry" in main_line
    assert ":::entry" not in helper_line


def test_project_graph_classdefs():
    project = AnalyzedProject(path="/tmp", scripts=[AnalyzedScript(path="a.py")])
    result = project_graph(project)
    assert "classDef api" in result
    assert "classDef entry" in result


# --- script_flow ---


def test_script_flow_empty():
    script = AnalyzedScript(path="empty.py", steps=[])
    result = script_flow(script)
    assert "graph TB" in result
    assert "No steps detected" in result


def test_script_flow_single_step():
    step = Step(line_number=5, type="api_call", description="requests.get()")
    script = AnalyzedScript(path="test.py", steps=[step])
    result = script_flow(script)
    assert "graph TB" in result
    assert "API: requests.get()" in result
    assert ":::api" in result


def test_script_flow_sequential_edges():
    steps = [
        Step(line_number=1, type="api_call", description="fetch()", function_name="main"),
        Step(line_number=2, type="output", description="print()", function_name="main"),
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script)
    assert "n_test_1 --> n_test_2" in result


def test_script_flow_function_subgraphs():
    steps = [
        Step(line_number=5, type="api_call", description="fetch()", function_name="fetch_data"),
        Step(line_number=10, type="file_io", description="save()", function_name="save_data"),
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script)
    assert "subgraph" in result
    assert "fetch_data()" in result
    assert "save_data()" in result


def test_script_flow_module_level_no_subgraph():
    steps = [
        Step(line_number=1, type="output", description="print()"),
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script)
    # Module-level steps should NOT be in a subgraph
    assert "subgraph" not in result


def test_script_flow_no_cross_function_edges():
    """Steps in different functions should NOT get sequential edges."""
    steps = [
        Step(line_number=5, type="api_call", description="fetch()", function_name="func_a"),
        Step(line_number=10, type="output", description="print()", function_name="func_b"),
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script)
    assert "n_test_5 --> n_test_10" not in result


def test_script_flow_classdefs():
    step = Step(line_number=1, type="transform", description="sorted()")
    script = AnalyzedScript(path="test.py", steps=[step])
    result = script_flow(script)
    assert "classDef transform" in result
    assert "classDef api" in result


def test_script_flow_all_step_types():
    """All 6 step types should render with correct shapes."""
    steps = [
        Step(line_number=1, type="api_call", description="a"),
        Step(line_number=2, type="file_io", description="b"),
        Step(line_number=3, type="db_op", description="c"),
        Step(line_number=4, type="decision", description="d"),
        Step(line_number=5, type="output", description="e"),
        Step(line_number=6, type="transform", description="f"),
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script)
    assert '["API: a"]:::api' in result
    assert '[/"File: b"/]:::fileio' in result
    assert '[("DB: c")]:::dbop' in result
    assert '{"d"}:::decision' in result
    assert '(["Output: e"]):::output' in result
    assert '[["Transform: f"]]:::transform' in result


# --- Integration with real fixtures ---


def test_project_graph_with_fixtures(fixtures_dir):
    """Project graph from agentic_workflows fixture should have scripts and connections."""
    agentic = fixtures_dir / "agentic_workflows"
    scripts = scan_project(agentic)
    connections = resolve_connections(scripts, agentic)
    project = AnalyzedProject(
        path=str(agentic),
        scripts=scripts,
        connections=connections,
        entry_points=[s.path for s in scripts if s.is_entry_point],
    )
    result = project_graph(project)
    assert "graph LR" in result
    # Should have at least some of the 8 agentic workflow scripts
    assert "scrape_google_maps" in result
    assert "gmaps_lead_pipeline" in result


def test_script_flow_with_hello_fixture(hello_script, fixtures_dir):
    """Script flow from hello.py fixture should have multiple step types."""
    script = analyze_file(hello_script, fixtures_dir)
    result = script_flow(script)
    assert "graph TB" in result
    assert ":::api" in result
    assert ":::fileio" in result
    assert ":::decision" in result
    assert "subgraph" in result  # hello.py has functions
