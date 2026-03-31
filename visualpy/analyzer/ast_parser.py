"""AST-based script analyzer — extract steps, function calls, imports, I/O, control flow."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from visualpy.models import AnalyzedScript, Service, Step
from visualpy.analyzer.service_map import detect_services
from visualpy.analyzer.signatures import parse_signature
from visualpy.analyzer.triggers import detect_triggers

_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB — skip generated mega-files

# Known API-call patterns: (object_attr, ...) that indicate an HTTP/API call
_API_METHODS = frozenset({"get", "post", "put", "patch", "delete", "head", "options", "request"})
_API_OBJECTS = frozenset({"requests", "httpx", "client", "session", "http", "aiohttp"})

# Known file I/O functions
_FILE_IO_NAMES = frozenset({"open"})
_FILE_IO_METHODS = frozenset({
    "read_text", "write_text", "read_bytes", "write_bytes",  # pathlib
    "dump", "dumps", "load", "loads",  # json
    "reader", "writer", "DictReader", "DictWriter",  # csv
})
_FILE_IO_MODULES = frozenset({"json", "csv", "pickle", "yaml", "toml"})

# Known DB patterns — guarded by _DB_OBJECTS to avoid false positives on common methods
_DB_METHODS = frozenset({
    "execute", "executemany", "fetchone", "fetchall", "fetchmany",
    "commit", "rollback", "cursor",
    "insert_one", "insert_many", "find", "find_one", "update_one", "delete_one",  # pymongo
    "query", "add", "flush",  # sqlalchemy
})
_DB_OBJECTS = frozenset({
    "cursor", "cur", "conn", "connection", "db", "database",
    "session", "engine", "collection", "table", "query",
})

# Known output functions
_OUTPUT_NAMES = frozenset({"print"})
_LOGGING_METHODS = frozenset({"info", "debug", "warning", "error", "critical", "exception"})


def analyze_file(file_path: Path, project_root: Path) -> AnalyzedScript:
    """Analyze a single Python file and produce an AnalyzedScript."""
    try:
        rel_path = str(file_path.relative_to(project_root))
    except ValueError:
        rel_path = str(file_path)

    # Skip oversized files (generated code, data-as-python, etc.)
    try:
        if file_path.stat().st_size > _MAX_FILE_SIZE:
            print(f"[visualpy] Warning: skipping {rel_path}: file exceeds 10 MB", file=sys.stderr)
            return AnalyzedScript(path=rel_path)
    except OSError:
        pass  # stat failed — try reading anyway

    try:
        source = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"[visualpy] Warning: skipping {rel_path}: {exc}", file=sys.stderr)
        return AnalyzedScript(path=rel_path)

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:
        print(f"[visualpy] Warning: skipping {rel_path}: syntax error: {exc}", file=sys.stderr)
        return AnalyzedScript(path=rel_path)

    # Extract imports
    imports_internal, imports_external = _extract_imports(tree, project_root)

    # Extract secrets
    secrets = _extract_secrets(tree)

    # Detect services from external imports
    services = detect_services(imports_external)

    # Detect triggers
    triggers = detect_triggers(tree, source)

    # Parse main() signature
    signature = parse_signature(tree)

    # Detect entry point
    is_entry_point = any(t.detail == "__main__ guard" for t in triggers)

    # Extract steps
    collector = _StepCollector(services)
    collector.visit(tree)
    steps = sorted(collector.steps, key=lambda s: s.line_number)

    return AnalyzedScript(
        path=rel_path,
        is_entry_point=is_entry_point,
        steps=steps,
        imports_internal=imports_internal,
        imports_external=imports_external,
        services=services,
        secrets=secrets,
        triggers=triggers,
        signature=signature,
    )


def _extract_imports(tree: ast.Module, project_root: Path) -> tuple[list[str], list[str]]:
    """Separate internal (project-local) from external imports."""
    internal: list[str] = []
    external: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                _classify_import(alias.name, project_root, internal, external)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _classify_import(node.module, project_root, internal, external)

    return sorted(set(internal)), sorted(set(external))


def _classify_import(module_name: str, project_root: Path, internal: list, external: list) -> None:
    """Check if a module corresponds to a local .py file."""
    top_level = module_name.split(".")[0]
    candidate = project_root / f"{top_level}.py"
    candidate_pkg = project_root / top_level / "__init__.py"
    try:
        is_local = candidate.exists() or candidate_pkg.exists()
    except OSError:
        is_local = False
    if is_local:
        internal.append(module_name)
    else:
        external.append(module_name)


def _extract_secrets(tree: ast.Module) -> list[str]:
    """Find os.getenv / os.environ usage and extract secret names."""
    secrets: set[str] = set()

    for node in ast.walk(tree):
        # os.getenv("KEY") or os.environ.get("KEY")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            func = node.func
            if func.attr == "getenv" and isinstance(func.value, ast.Name) and func.value.id == "os":
                if node.args and isinstance(node.args[0], ast.Constant):
                    secrets.add(node.args[0].value)
            elif func.attr == "get" and isinstance(func.value, ast.Attribute):
                if func.value.attr == "environ" and isinstance(func.value.value, ast.Name) and func.value.value.id == "os":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        secrets.add(node.args[0].value)

        # os.environ["KEY"] via subscript
        elif isinstance(node, ast.Subscript):
            if (
                isinstance(node.value, ast.Attribute)
                and node.value.attr == "environ"
                and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os"
            ):
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    secrets.add(node.slice.value)

    return sorted(secrets)


class _StepCollector(ast.NodeVisitor):
    """Walk AST and collect Steps ordered by line number.

    Classifies each significant node as: api_call, file_io, db_op,
    transform, decision, or output.
    """

    def __init__(self, services: list[Service]) -> None:
        self.steps: list[Step] = []
        self.services = services
        self._service_libs = {s.library for s in services}
        self._current_func: str | None = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev = self._current_func
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = prev

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_If(self, node: ast.If) -> None:
        cond = _safe_unparse(node.test)
        # Skip __main__ guard — it's a trigger, not a decision step
        if "__name__" in cond and "__main__" in cond:
            self.generic_visit(node)
            return
        self._add_step(node.lineno, "decision", f"if {cond}")
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        target = _safe_unparse(node.target)
        iter_expr = _safe_unparse(node.iter)
        self._add_step(node.lineno, "decision", f"for {target} in {iter_expr}")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        cond = _safe_unparse(node.test)
        self._add_step(node.lineno, "decision", f"while {cond}")
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self._add_step(node.lineno, "decision", "try/except block")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._classify_call(node)
        self.generic_visit(node)

    def _classify_call(self, node: ast.Call) -> None:
        """Classify a Call node into a step type."""
        func = node.func
        line = node.lineno

        # --- ast.Attribute calls: obj.method(...) ---
        if isinstance(func, ast.Attribute):
            method = func.attr
            obj_name = _resolve_object_name(func.value)

            # API call: requests.get(), client.post(), etc.
            if method in _API_METHODS and obj_name in _API_OBJECTS:
                desc = f"{obj_name}.{method}()"
                svc = self._match_service(obj_name)
                self._add_step(line, "api_call", desc, service=svc)
                return

            # File I/O: json.dump(), csv.reader(), pathlib methods
            if method in _FILE_IO_METHODS and obj_name in _FILE_IO_MODULES:
                self._add_step(line, "file_io", f"{obj_name}.{method}()")
                return
            if method in _FILE_IO_METHODS:
                self._add_step(line, "file_io", f".{method}()")
                return

            # DB operations
            if method in _DB_METHODS and obj_name in _DB_OBJECTS:
                self._add_step(line, "db_op", f"{obj_name}.{method}()" if obj_name else f".{method}()")
                return

            # Output: logging.*
            if method in _LOGGING_METHODS and obj_name in ("logging", "logger", "log"):
                self._add_step(line, "output", f"{obj_name}.{method}()")
                return

            # Known service SDK calls (e.g., openai.ChatCompletion.create())
            if obj_name in self._service_libs:
                svc = self._match_service(obj_name)
                self._add_step(line, "api_call", f"{obj_name}.{method}()", service=svc)
                return

            return

        # --- ast.Name calls: func_name(...) ---
        if isinstance(func, ast.Name):
            name = func.id

            # Built-in output
            if name in _OUTPUT_NAMES:
                self._add_step(line, "output", f"{name}()")
                return

            # File I/O: open()
            if name in _FILE_IO_NAMES:
                path_arg = _extract_first_str_arg(node)
                desc = f"open({path_arg!r})" if path_arg else "open()"
                self._add_step(line, "file_io", desc)
                return

            return

    def _match_service(self, obj_name: str) -> Service | None:
        """Find a Service object matching an object name."""
        for svc in self.services:
            if svc.library == obj_name or obj_name.startswith(svc.library):
                return svc
        return None

    def _add_step(
        self,
        line: int,
        step_type: str,
        description: str,
        service: Service | None = None,
    ) -> None:
        self.steps.append(
            Step(
                line_number=line,
                type=step_type,
                description=description,
                function_name=self._current_func,
                service=service,
            )
        )


def _safe_unparse(node: ast.AST) -> str:
    """ast.unparse() with fallback for malformed nodes."""
    try:
        return ast.unparse(node)
    except (ValueError, TypeError):
        return "<expression>"


def _resolve_object_name(node: ast.expr) -> str:
    """Resolve the object name from an attribute chain.

    E.g. `requests.get(...)` → "requests"
         `self.client.post(...)` → "client"
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _extract_first_str_arg(node: ast.Call) -> str | None:
    """Extract the first string constant argument from a call."""
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return None
