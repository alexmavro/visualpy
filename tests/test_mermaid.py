"""Tests for Mermaid syntax generation."""

from visualpy.analyzer.ast_parser import analyze_file
from visualpy.analyzer.cross_file import resolve_connections
from visualpy.analyzer.scanner import scan_project
from visualpy.mermaid import (
    _compact_function_node,
    _escape_label,
    _sanitize_id,
    _step_node,
    importance_score,
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


# --- _compact_function_node ---


def test_compact_function_node_label():
    steps = [
        Step(line_number=i, type="api_call", description=f"call{i}")
        for i in range(10)
    ]
    result = _compact_function_node("fetch_data", steps, "test")
    assert "fetch_data()" in result
    assert "10 steps" in result
    assert "10 API" in result


def test_compact_function_node_shape():
    steps = [Step(line_number=1, type="transform", description="x")]
    result = _compact_function_node("func", steps, "test")
    assert '[[' in result
    assert ']]' in result
    assert ":::compact" in result


def test_compact_function_node_multiple_types():
    steps = [
        Step(line_number=1, type="api_call", description="a"),
        Step(line_number=2, type="api_call", description="b"),
        Step(line_number=3, type="file_io", description="c"),
        Step(line_number=4, type="decision", description="d"),
    ]
    result = _compact_function_node("func", steps, "test")
    assert "4 steps" in result
    assert "2 API" in result
    assert "1 File I/O" in result
    assert "1 Decision" in result


# --- script_flow compact mode ---


def test_compact_collapses_large_functions():
    """Functions with more steps than threshold are collapsed."""
    steps = [
        Step(line_number=i, type="api_call", description=f"call{i}", function_name="big_func")
        for i in range(12)
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script, compact=True, compact_threshold=8)
    assert "big_func()" in result
    assert "12 steps" in result
    assert ":::compact" in result
    # Should NOT have individual step nodes
    assert "n_test_0" not in result
    # Should NOT have a subgraph
    assert "subgraph" not in result


def test_compact_keeps_small_functions():
    """Functions with steps at or below threshold stay expanded."""
    steps = [
        Step(line_number=i, type="api_call", description=f"call{i}", function_name="small_func")
        for i in range(5)
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script, compact=True, compact_threshold=8)
    # Should have individual step nodes (not collapsed)
    assert "n_test_0" in result
    assert "subgraph" in result
    assert ":::compact" not in result


def test_compact_module_level_never_collapsed():
    """Module-level steps (_module_) are never collapsed even in compact mode."""
    steps = [
        Step(line_number=i, type="output", description=f"print{i}")
        for i in range(20)
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script, compact=True, compact_threshold=8)
    # Module level steps should all be present individually
    assert "n_test_0" in result
    assert "n_test_19" in result
    assert ":::compact" not in result


def test_compact_threshold_boundary():
    """Function with exactly threshold steps stays expanded; threshold+1 collapses."""
    steps_at = [
        Step(line_number=i, type="api_call", description=f"c{i}", function_name="func")
        for i in range(8)
    ]
    script_at = AnalyzedScript(path="test.py", steps=steps_at)
    result_at = script_flow(script_at, compact=True, compact_threshold=8)
    assert ":::compact" not in result_at  # stays expanded

    steps_over = steps_at + [
        Step(line_number=8, type="api_call", description="c8", function_name="func")
    ]
    script_over = AnalyzedScript(path="test.py", steps=steps_over)
    result_over = script_flow(script_over, compact=True, compact_threshold=8)
    assert ":::compact" in result_over  # collapsed


def test_compact_no_internal_edges():
    """Collapsed functions should have no --> edges."""
    steps = [
        Step(line_number=i, type="api_call", description=f"c{i}", function_name="big")
        for i in range(12)
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script, compact=True, compact_threshold=8)
    assert "-->" not in result


def test_compact_classdefs():
    steps = [
        Step(line_number=i, type="api_call", description=f"c{i}", function_name="big")
        for i in range(12)
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result = script_flow(script, compact=True)
    assert "classDef compact" in result


def test_compact_default_is_false():
    """script_flow() without compact arg produces same output as compact=False."""
    steps = [
        Step(line_number=i, type="api_call", description=f"c{i}", function_name="big")
        for i in range(12)
    ]
    script = AnalyzedScript(path="test.py", steps=steps)
    result_default = script_flow(script)
    result_explicit = script_flow(script, compact=False)
    assert result_default == result_explicit
    # Should have individual steps, not compact
    assert ":::compact" not in result_default
    assert "n_test_0" in result_default


# --- importance_score ---


def test_importance_entry_point_bonus():
    script = AnalyzedScript(path="main.py", is_entry_point=True)
    project = AnalyzedProject(path="/tmp", scripts=[script], entry_points=["main.py"])
    score = importance_score(script, project)
    assert score >= 2  # entry point bonus


def test_importance_connections():
    scripts = [AnalyzedScript(path="a.py"), AnalyzedScript(path="b.py")]
    connections = [
        ScriptConnection(source="a.py", target="b.py", type="import", detail=""),
        ScriptConnection(source="b.py", target="a.py", type="file_io", detail=""),
    ]
    project = AnalyzedProject(path="/tmp", scripts=scripts, connections=connections)
    score_a = importance_score(scripts[0], project)
    assert score_a >= 2  # 1 out + 1 in


def test_importance_services():
    script = AnalyzedScript(
        path="api.py",
        services=[Service(name="S1", library="l1"), Service(name="S2", library="l2")],
    )
    project = AnalyzedProject(path="/tmp", scripts=[script])
    score = importance_score(script, project)
    assert score >= 2  # 2 services


def test_importance_step_bonus_capped():
    steps = [Step(line_number=i, type="output", description="x") for i in range(200)]
    script = AnalyzedScript(path="big.py", steps=steps)
    project = AnalyzedProject(path="/tmp", scripts=[script])
    score = importance_score(script, project)
    # 200 steps // 20 = 10, but capped at 5
    assert score == 5


def test_importance_isolated_script():
    script = AnalyzedScript(path="lonely.py", steps=[Step(line_number=1, type="output", description="x")])
    project = AnalyzedProject(path="/tmp", scripts=[script])
    score = importance_score(script, project)
    assert score == 0  # 1 step // 20 = 0, no connections, no entry, no services


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
