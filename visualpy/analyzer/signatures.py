"""Signature parser — extract main() type hints for auto-UI metadata."""

from __future__ import annotations

import ast


def parse_signature(tree: ast.Module) -> dict | None:
    """Find main() and extract its parameter names, type annotations, and defaults.

    Returns None if no main() found. Otherwise returns:
        {"param_name": {"type": "str", "default": "value"}, ...}
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "main":
            continue

        args = node.args
        params: dict[str, dict] = {}

        # Defaults are right-aligned: if 3 args and 1 default, default applies to arg[2]
        num_args = len(args.args)
        num_defaults = len(args.defaults)
        default_offset = num_args - num_defaults

        for i, arg in enumerate(args.args):
            if arg.arg == "self":
                continue
            info: dict = {}
            if arg.annotation:
                info["type"] = ast.unparse(arg.annotation)
            default_idx = i - default_offset
            if default_idx >= 0:
                info["default"] = _eval_default(args.defaults[default_idx])
            params[arg.arg] = info

        return params if params else None

    return None


def _eval_default(node: ast.expr):
    """Safely extract a default value from an AST node."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return [_eval_default(el) for el in node.elts]
    if isinstance(node, ast.Dict):
        return {
            _eval_default(k) if k else None: _eval_default(v)
            for k, v in zip(node.keys, node.values)
        }
    if isinstance(node, (ast.Name, ast.Attribute)):
        return ast.unparse(node)
    return ast.unparse(node)
