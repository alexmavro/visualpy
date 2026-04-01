"""FastAPI server — serves web UI for visual exploration."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from visualpy.mermaid import importance_score, project_graph, script_flow
from visualpy.models import AnalyzedProject

_PACKAGE_DIR = Path(__file__).parent
_TEMPLATES_DIR = _PACKAGE_DIR / "templates"
_STATIC_DIR = _PACKAGE_DIR.parent / "static"


def create_app(project: AnalyzedProject) -> FastAPI:
    """Build a FastAPI application pre-loaded with analysis results."""
    app = FastAPI(title="visualpy", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    # Pre-compute project graph once (graceful fallback on error).
    try:
        app.state.project_graph = project_graph(project)
    except Exception as exc:
        print(f"[visualpy] Warning: failed to build project graph: {exc}", file=sys.stderr)
        app.state.project_graph = 'graph LR\n  error["Graph generation failed"]'

    app.state.project = project
    app.state.scripts_by_path = {s.path: s for s in project.scripts}

    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    else:
        print(
            f"[visualpy] Warning: static directory not found at {_STATIC_DIR}, "
            "CSS will not load",
            file=sys.stderr,
        )

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        print(f"[visualpy] Error handling {request.url}: {exc}", file=sys.stderr)
        return templates.TemplateResponse(
            request,
            "error.html",
            context={"message": "Something went wrong rendering this page.", "code": 500},
            status_code=500,
        )

    @app.get("/", response_class=HTMLResponse)
    async def overview(request: Request):
        scored = sorted(
            project.scripts,
            key=lambda s: importance_score(s, project),
            reverse=True,
        )
        # Top ~30% of scripts are "key" scripts (at least 1).
        key_count = max(1, len(scored) // 3)
        key_paths = {s.path for s in scored[:key_count]}
        return templates.TemplateResponse(
            request,
            "overview.html",
            context={
                "project": project,
                "graph": app.state.project_graph,
                "sorted_scripts": scored,
                "key_paths": key_paths,
            },
        )

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok"})

    @app.get("/script/{path:path}", response_class=HTMLResponse)
    async def script_view(request: Request, path: str):
        script = app.state.scripts_by_path.get(path)
        if script is None:
            return templates.TemplateResponse(
                request,
                "error.html",
                context={"message": f"Script not found: {path}", "code": 404},
                status_code=404,
            )
        try:
            flow_detailed = script_flow(script)
        except Exception as exc:
            print(f"[visualpy] Warning: failed to build detailed flow for {path}: {exc}", file=sys.stderr)
            flow_detailed = 'graph TB\n  error["Flow generation failed for this script"]'
        try:
            flow_compact = script_flow(script, compact=True)
        except Exception as exc:
            print(f"[visualpy] Warning: failed to build compact flow for {path}: {exc}", file=sys.stderr)
            flow_compact = 'graph TB\n  error["Compact flow generation failed"]'
        total_steps = len(script.steps)
        return templates.TemplateResponse(
            request,
            "script.html",
            context={
                "project": project,
                "script": script,
                "flow": flow_compact if total_steps > 30 else flow_detailed,
                "flow_detailed": flow_detailed,
                "flow_compact": flow_compact,
                "total_steps": total_steps,
                "default_compact": total_steps > 30,
            },
        )

    @app.get("/partials/step/{path:path}/{line}", response_class=HTMLResponse)
    async def step_detail(request: Request, path: str, line: int):
        script = app.state.scripts_by_path.get(path)
        if script is None:
            return HTMLResponse(
                '<p class="text-sm text-red-600 dark:text-red-400">Script not found.</p>',
                status_code=404,
            )
        step = next((s for s in script.steps if s.line_number == line), None)
        if step is None:
            return HTMLResponse(
                '<p class="text-sm text-red-600 dark:text-red-400">Step not found at this line.</p>',
                status_code=404,
            )
        return templates.TemplateResponse(
            request,
            "partials/step_detail.html",
            context={"step": step, "script_path": path},
        )

    return app
