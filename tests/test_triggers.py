"""Tests for triggers module."""

import ast

from visualpy.analyzer.triggers import detect_triggers


def test_main_guard():
    code = '''
if __name__ == "__main__":
    main()
'''
    tree = ast.parse(code)
    triggers = detect_triggers(tree, code)
    assert any(t.type == "cli" and t.detail == "__main__ guard" for t in triggers)


def test_argparse():
    code = '''
import argparse
parser = argparse.ArgumentParser()
'''
    tree = ast.parse(code)
    triggers = detect_triggers(tree, code)
    assert any(t.type == "cli" and t.detail == "argparse" for t in triggers)


def test_fastapi_route():
    code = '''
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/webhook/intake")
def intake(data: dict):
    return data
'''
    tree = ast.parse(code)
    triggers = detect_triggers(tree, code)
    webhooks = [t for t in triggers if t.type == "webhook"]
    assert len(webhooks) == 2
    assert any("GET /health" in t.detail for t in webhooks)
    assert any("POST /webhook/intake" in t.detail for t in webhooks)


def test_click_command():
    code = '''
import click

@click.command()
def cli():
    pass
'''
    tree = ast.parse(code)
    triggers = detect_triggers(tree, code)
    assert any(t.type == "cli" and "click/typer" in t.detail for t in triggers)


def test_schedule_job():
    code = '''
import schedule
schedule.every(5).minutes.do(my_func)
'''
    tree = ast.parse(code)
    triggers = detect_triggers(tree, code)
    assert any(t.type == "cron" for t in triggers)


def test_hello_fixture(hello_script):
    tree = ast.parse(hello_script.read_text())
    triggers = detect_triggers(tree, hello_script.read_text())
    assert any(t.type == "cli" and t.detail == "__main__ guard" for t in triggers)


def test_no_triggers():
    code = "x = 1 + 2"
    tree = ast.parse(code)
    triggers = detect_triggers(tree, code)
    assert triggers == []


def test_deduplication():
    code = '''
if __name__ == "__main__":
    pass
if __name__ == "__main__":
    pass
'''
    tree = ast.parse(code)
    triggers = detect_triggers(tree, code)
    main_guards = [t for t in triggers if t.detail == "__main__ guard"]
    assert len(main_guards) == 1


def test_modal_endpoint():
    code = '''
import modal

@modal.web_endpoint()
def predict(data: dict):
    return {"result": "ok"}
'''
    tree = ast.parse(code)
    triggers = detect_triggers(tree, code)
    assert any(t.type == "webhook" and "modal endpoint" in t.detail for t in triggers)
