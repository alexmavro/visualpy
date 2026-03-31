"""Tests for signatures module."""

import ast

from visualpy.analyzer.signatures import parse_signature


def test_hello_fixture(hello_script):
    tree = ast.parse(hello_script.read_text())
    sig = parse_signature(tree)
    assert sig is not None
    assert "url" in sig
    assert sig["url"]["type"] == "str"
    assert "output" in sig
    assert sig["output"]["type"] == "str"
    assert sig["output"]["default"] == "output.json"
    assert "verbose" in sig
    assert sig["verbose"]["type"] == "bool"
    assert sig["verbose"]["default"] is False


def test_no_main():
    tree = ast.parse("def helper(): pass")
    assert parse_signature(tree) is None


def test_no_params():
    tree = ast.parse("def main(): pass")
    assert parse_signature(tree) is None


def test_untyped_params():
    tree = ast.parse("def main(x, y=10): pass")
    sig = parse_signature(tree)
    assert sig is not None
    assert "x" in sig
    assert "type" not in sig["x"]
    assert sig["y"]["default"] == 10


def test_complex_defaults():
    code = 'def main(items: list = [], config: dict = {"a": 1}): pass'
    tree = ast.parse(code)
    sig = parse_signature(tree)
    assert sig is not None
    assert sig["items"]["default"] == []
    assert sig["config"]["default"] == {"a": 1}
