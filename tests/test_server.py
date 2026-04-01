"""Tests for the FastAPI web server."""

import pytest
from httpx import ASGITransport, AsyncClient

from visualpy.analyzer.ast_parser import analyze_file
from visualpy.analyzer.cross_file import resolve_connections
from visualpy.analyzer.scanner import scan_project
from visualpy.models import AnalyzedProject, AnalyzedScript, ScriptConnection, Step
from visualpy.server import create_app


@pytest.fixture
def simple_project():
    """Minimal project with one script and a few steps."""
    steps = [
        Step(line_number=5, type="api_call", description="requests.get()", function_name="fetch"),
        Step(line_number=10, type="decision", description="if ok", function_name="fetch"),
        Step(line_number=12, type="output", description="print(result)", function_name="fetch"),
    ]
    script = AnalyzedScript(
        path="example.py",
        is_entry_point=True,
        steps=steps,
        secrets=["API_KEY"],
    )
    return AnalyzedProject(
        path="/tmp/test",
        scripts=[script],
        entry_points=["example.py"],
        secrets=["API_KEY"],
    )


@pytest.fixture
def multi_project():
    """Project with two connected scripts."""
    scripts = [
        AnalyzedScript(path="a.py", is_entry_point=True, steps=[
            Step(line_number=1, type="api_call", description="fetch()"),
        ]),
        AnalyzedScript(path="b.py", steps=[
            Step(line_number=1, type="file_io", description="save()"),
        ]),
    ]
    connections = [
        ScriptConnection(source="a.py", target="b.py", type="import", detail="a imports b"),
    ]
    return AnalyzedProject(
        path="/tmp/multi",
        scripts=scripts,
        connections=connections,
        entry_points=["a.py"],
    )


@pytest.fixture
def client(simple_project):
    app = create_app(simple_project)
    return app


@pytest.fixture
def multi_client(multi_project):
    app = create_app(multi_project)
    return app


# --- Health ---

@pytest.mark.anyio
async def test_health(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- Overview ---

@pytest.mark.anyio
async def test_overview_returns_200(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


@pytest.mark.anyio
async def test_overview_contains_mermaid(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "mermaid" in resp.text.lower()


@pytest.mark.anyio
async def test_overview_shows_project_path(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "/tmp/test" in resp.text


@pytest.mark.anyio
async def test_overview_shows_script_card(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "example.py" in resp.text
    assert "/script/example.py" in resp.text


@pytest.mark.anyio
async def test_overview_shows_entry_point_badge(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "entry" in resp.text.lower()


@pytest.mark.anyio
async def test_overview_shows_secrets(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "API_KEY" in resp.text


@pytest.mark.anyio
async def test_overview_project_graph_with_connections(multi_client):
    async with AsyncClient(transport=ASGITransport(app=multi_client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "graph LR" in resp.text
    assert "import" in resp.text


# --- Script view ---

@pytest.mark.anyio
async def test_script_view_returns_200(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_script_view_contains_flow(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "graph TB" in resp.text


@pytest.mark.anyio
async def test_script_view_shows_step_types(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "api" in resp.text
    assert "decision" in resp.text


@pytest.mark.anyio
async def test_script_view_has_breadcrumb(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "visualpy" in resp.text
    assert "example.py" in resp.text


@pytest.mark.anyio
async def test_script_view_shows_secrets(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "API_KEY" in resp.text


@pytest.mark.anyio
async def test_script_not_found(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/nonexistent.py")
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


# --- Step detail partial ---

@pytest.mark.anyio
async def test_step_detail_returns_fragment(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/partials/step/example.py/5")
    assert resp.status_code == 200
    assert "API Call" in resp.text
    assert "requests.get()" in resp.text


@pytest.mark.anyio
async def test_step_detail_shows_function_name(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/partials/step/example.py/5")
    assert "fetch()" in resp.text


@pytest.mark.anyio
async def test_step_detail_not_found_script(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/partials/step/nope.py/1")
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


@pytest.mark.anyio
async def test_step_detail_not_found_line(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/partials/step/example.py/999")
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


# --- Dark mode toggle ---

@pytest.mark.anyio
async def test_dark_mode_toggle_present(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "dark-toggle" in resp.text


# --- UX features ---

@pytest.mark.anyio
async def test_script_view_has_color_legend(client):
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "API Call" in resp.text
    assert "File I/O" in resp.text
    assert "Database" in resp.text


@pytest.mark.anyio
async def test_script_view_has_step_list(client):
    """Fallback step list should always be visible."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "All Steps" in resp.text
    assert "requests.get()" in resp.text


@pytest.mark.anyio
async def test_script_view_has_step_detail_placeholder(client):
    """Step detail panel should be visible with placeholder text."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "Select a step" in resp.text


@pytest.mark.anyio
async def test_overview_inventory_always_shown(client):
    """Services and secrets panels should always be visible."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "Services" in resp.text
    assert "Secrets" in resp.text


@pytest.mark.anyio
async def test_overview_empty_project():
    """Empty project should show friendly message."""
    project = AnalyzedProject(path="/tmp/empty")
    app = create_app(project)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert resp.status_code == 200
    assert "No Python scripts found" in resp.text
    assert "No external services detected" in resp.text


@pytest.mark.anyio
async def test_overview_single_script_shortcut():
    """Single-script project should show direct link to script view."""
    script = AnalyzedScript(path="only.py", is_entry_point=True)
    project = AnalyzedProject(path="/tmp/one", scripts=[script], entry_points=["only.py"])
    app = create_app(project)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "View only.py flow" in resp.text
    assert "/script/only.py" in resp.text


@pytest.mark.anyio
async def test_script_not_found_shows_error_code(client):
    """404 page should show 404 code, not hardcoded."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/nonexistent.py")
    assert "404" in resp.text
    assert "not found" in resp.text.lower()


@pytest.mark.anyio
async def test_back_navigation_present(client):
    """Script view should have back arrow navigation."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "&larr;" in resp.text or "←" in resp.text


@pytest.mark.anyio
async def test_mermaid_rerender_function_present(client):
    """base.html should include reRenderMermaid for dark mode toggle."""
    async with AsyncClient(transport=ASGITransport(app=client), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "reRenderMermaid" in resp.text


# --- LLM summary rendering ---


@pytest.mark.anyio
async def test_overview_shows_project_summary():
    project = AnalyzedProject(
        path="/tmp/test",
        scripts=[AnalyzedScript(path="a.py")],
        summary="This project automates lead generation.",
    )
    app = create_app(project)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "This project automates lead generation." in resp.text


@pytest.mark.anyio
async def test_overview_no_summary_no_crash():
    project = AnalyzedProject(path="/tmp/test", scripts=[AnalyzedScript(path="a.py")])
    app = create_app(project)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert resp.status_code == 200
    assert "lead generation" not in resp.text


@pytest.mark.anyio
async def test_script_view_shows_summary():
    script = AnalyzedScript(
        path="example.py",
        summary="Fetches data from an API and saves it locally.",
    )
    project = AnalyzedProject(path="/tmp/test", scripts=[script])
    app = create_app(project)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/script/example.py")
    assert "Fetches data from an API and saves it locally." in resp.text


@pytest.mark.anyio
async def test_script_card_shows_summary():
    script = AnalyzedScript(
        path="example.py",
        summary="Automates data fetching.",
    )
    project = AnalyzedProject(path="/tmp/test", scripts=[script])
    app = create_app(project)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert "Automates data fetching." in resp.text


# --- Integration with real fixtures ---

@pytest.mark.anyio
async def test_overview_with_agentic_fixtures(fixtures_dir):
    """Full integration: analyze agentic_workflows and serve."""
    agentic = fixtures_dir / "agentic_workflows"
    scripts = scan_project(agentic)
    connections = resolve_connections(scripts, agentic)
    project = AnalyzedProject(
        path=str(agentic),
        scripts=scripts,
        connections=connections,
        entry_points=[s.path for s in scripts if s.is_entry_point],
        services=[svc for s in scripts for svc in s.services],
        secrets=sorted({sec for s in scripts for sec in s.secrets}),
    )
    app = create_app(project)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/")
    assert resp.status_code == 200
    assert "scrape_google_maps" in resp.text


@pytest.mark.anyio
async def test_script_view_with_hello_fixture(hello_script, fixtures_dir):
    """Serve hello.py and check flow rendering."""
    script = analyze_file(hello_script, fixtures_dir)
    project = AnalyzedProject(
        path=str(fixtures_dir), scripts=[script], entry_points=[script.path]
    )
    app = create_app(project)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get(f"/script/{script.path}")
    assert resp.status_code == 200
    assert "graph TB" in resp.text
