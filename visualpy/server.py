"""FastAPI server — serves web UI for visual exploration."""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from visualpy.mermaid import importance_score, pedagogical_flow, project_graph, script_flow
from visualpy.models import AnalyzedProject
from visualpy.translate import (
    BUSINESS_LABELS,
    TECHNICAL_LABELS,
    TECHNICAL_LABELS_SHORT,
    translate_connection,
    translate_secret,
    translate_step,
    translate_trigger,
)

_PACKAGE_DIR = Path(__file__).parent
_TEMPLATES_DIR = _PACKAGE_DIR / "templates"
_STATIC_DIR = _PACKAGE_DIR.parent / "static"


def create_app(project: AnalyzedProject) -> FastAPI:
    """Build a FastAPI application pre-loaded with analysis results."""
    app = FastAPI(title="visualpy", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    # Register translation functions as Jinja2 globals for all templates.
    templates.env.globals["biz_labels"] = BUSINESS_LABELS
    templates.env.globals["tech_labels"] = TECHNICAL_LABELS
    templates.env.globals["tech_labels_short"] = TECHNICAL_LABELS_SHORT
    templates.env.globals["translate_step"] = translate_step
    templates.env.globals["translate_trigger"] = translate_trigger
    templates.env.globals["translate_secret"] = translate_secret
    templates.env.globals["translate_connection"] = translate_connection

    # Phase inference globals (Sprint 6.5).
    from visualpy.translate import PHASE_LABELS, group_steps_by_phase, infer_phase
    templates.env.globals["infer_phase"] = infer_phase
    templates.env.globals["group_steps_by_phase"] = group_steps_by_phase
    templates.env.globals["phase_labels"] = PHASE_LABELS

    # Fallback diagrams for error cases.
    _GRAPH_FALLBACK = 'graph LR\n  error["Graph generation failed"]'
    _FLOW_FALLBACK = 'graph TB\n  error["Flow generation failed for this script"]'
    try:
        app.state.project_graph = project_graph(project)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(f"[visualpy] Warning: failed to build project graph: {exc}", file=sys.stderr)
        app.state.project_graph = _GRAPH_FALLBACK
    try:
        app.state.project_graph_biz = project_graph(project, business=True)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(f"[visualpy] Warning: failed to build business project graph: {exc}", file=sys.stderr)
        # Fall back to technical graph (better than error placeholder).
        app.state.project_graph_biz = app.state.project_graph

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
                "graph_biz": app.state.project_graph_biz,
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
        def _gen_flow(**kwargs: object) -> str:
            try:
                return script_flow(script, **kwargs)
            except Exception as exc:
                traceback.print_exc(file=sys.stderr)
                label = ", ".join(f"{k}={v}" for k, v in kwargs.items()) or "detailed"
                print(f"[visualpy] Warning: failed to build {label} flow for {path}: {exc}", file=sys.stderr)
                return _FLOW_FALLBACK

        flow_detailed = _gen_flow()
        flow_compact = _gen_flow(compact=True)
        # Business flows fall back to their technical counterparts on error.
        flow_detailed_biz = _gen_flow(business=True)
        if flow_detailed_biz == _FLOW_FALLBACK:
            flow_detailed_biz = flow_detailed
        flow_compact_biz = _gen_flow(compact=True, business=True)
        if flow_compact_biz == _FLOW_FALLBACK:
            flow_compact_biz = flow_compact

        # Pedagogical flow: simple phase pipeline for business view.
        try:
            flow_pedagogical = pedagogical_flow(script)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            print(f"[visualpy] Warning: failed to build pedagogical flow for {path}: {exc}", file=sys.stderr)
            flow_pedagogical = _FLOW_FALLBACK

        total_steps = len(script.steps)
        try:
            phase_groups = group_steps_by_phase(script.steps)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            print(f"[visualpy] Warning: failed to group steps by phase for {path}: {exc}", file=sys.stderr)
            phase_groups = []
        return templates.TemplateResponse(
            request,
            "script.html",
            context={
                "project": project,
                "script": script,
                "flow": flow_compact if total_steps > 30 else flow_detailed,
                "flow_detailed": flow_detailed,
                "flow_compact": flow_compact,
                "flow_detailed_biz": flow_detailed_biz,
                "flow_compact_biz": flow_compact_biz,
                "flow_pedagogical": flow_pedagogical,
                "phase_groups": phase_groups,
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
