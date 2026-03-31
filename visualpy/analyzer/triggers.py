"""Trigger detector — cron patterns, webhook decorators, CLI entry points."""

from __future__ import annotations

import ast

from visualpy.models import Trigger


def detect_triggers(tree: ast.Module, source: str) -> list[Trigger]:
    """Detect how a script gets invoked.

    Checks for:
    - if __name__ == "__main__" guard
    - argparse usage
    - Click / Typer CLI decorators
    - Flask / FastAPI route decorators (webhooks)
    - schedule / apscheduler (cron)
    """
    triggers: list[Trigger] = []

    for node in ast.walk(tree):
        # __main__ guard
        if isinstance(node, ast.If):
            _check_main_guard(node, triggers)

        # argparse
        if isinstance(node, ast.Call):
            _check_argparse(node, triggers)

        # Decorators on functions
        if isinstance(node, ast.FunctionDef):
            _check_decorators(node, triggers)

        # schedule library calls
        if isinstance(node, ast.Call):
            _check_schedule(node, triggers)

    return _deduplicate(triggers)


def _check_main_guard(node: ast.If, triggers: list[Trigger]) -> None:
    """Detect `if __name__ == "__main__":`."""
    test = node.test
    if not isinstance(test, ast.Compare):
        return
    if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
        return
    if len(test.comparators) != 1:
        return
    comp = test.comparators[0]
    if isinstance(comp, ast.Constant) and comp.value == "__main__":
        triggers.append(Trigger(type="cli", detail="__main__ guard"))


def _check_argparse(node: ast.Call, triggers: list[Trigger]) -> None:
    """Detect argparse.ArgumentParser() instantiation."""
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr == "ArgumentParser":
        if isinstance(func.value, ast.Name) and func.value.id == "argparse":
            triggers.append(Trigger(type="cli", detail="argparse"))
    elif isinstance(func, ast.Name) and func.id == "ArgumentParser":
        triggers.append(Trigger(type="cli", detail="argparse"))


def _check_decorators(node: ast.FunctionDef, triggers: list[Trigger]) -> None:
    """Detect CLI and webhook decorators."""
    for dec in node.decorator_list:
        dec_str = ast.unparse(dec)

        # Click / Typer
        if "click.command" in dec_str or "typer.command" in dec_str:
            triggers.append(Trigger(type="cli", detail=f"click/typer: {node.name}"))
        elif dec_str.startswith("app.command") or dec_str.startswith("cli.command"):
            triggers.append(Trigger(type="cli", detail=f"click/typer: {node.name}"))

        # FastAPI / Flask routes
        if any(
            method in dec_str
            for method in (".get(", ".post(", ".put(", ".delete(", ".patch(", ".route(")
        ):
            route = _extract_route(dec)
            method = _extract_method(dec_str)
            triggers.append(
                Trigger(type="webhook", detail=f"{method} {route}")
            )

        # Modal
        if "modal.web_endpoint" in dec_str or "modal.asgi_app" in dec_str:
            triggers.append(Trigger(type="webhook", detail=f"modal endpoint: {node.name}"))
        if "modal.function" in dec_str or "modal.method" in dec_str:
            triggers.append(Trigger(type="webhook", detail=f"modal function: {node.name}"))


def _check_schedule(node: ast.Call, triggers: list[Trigger]) -> None:
    """Detect schedule / apscheduler cron patterns."""
    func = node.func
    if isinstance(func, ast.Attribute):
        # schedule.every(5).minutes.do(...)
        if func.attr == "do":
            triggers.append(Trigger(type="cron", detail="schedule job"))
        # apscheduler: scheduler.add_job(...)
        if func.attr == "add_job":
            triggers.append(Trigger(type="cron", detail="apscheduler job"))


def _extract_route(dec: ast.expr) -> str:
    """Pull the route string from a decorator like @app.get("/path")."""
    if isinstance(dec, ast.Call) and dec.args:
        first_arg = dec.args[0]
        if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
            return first_arg.value
    return "<dynamic>"


def _extract_method(dec_str: str) -> str:
    """Infer HTTP method from decorator string."""
    for method in ("get", "post", "put", "delete", "patch"):
        if f".{method}(" in dec_str:
            return method.upper()
    return "ANY"


def _deduplicate(triggers: list[Trigger]) -> list[Trigger]:
    """Remove duplicate triggers (same type + detail)."""
    seen: set[tuple[str, str]] = set()
    result: list[Trigger] = []
    for t in triggers:
        key = (t.type, t.detail)
        if key not in seen:
            seen.add(key)
            result.append(t)
    return result
