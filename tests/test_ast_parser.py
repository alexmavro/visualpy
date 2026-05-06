"""Tests for ast_parser module."""

from pathlib import Path

from visualpy.analyzer.ast_parser import analyze_file


def test_hello_fixture(hello_script, fixtures_dir):
    result = analyze_file(hello_script, fixtures_dir)

    # Path is relative to project root
    assert result.path == "hello.py"

    # Entry point detected
    assert result.is_entry_point is True

    # Secrets: MY_API_KEY
    assert "MY_API_KEY" in result.secrets

    # Services: requests → HTTP Client
    assert any(s.name == "HTTP Client" for s in result.services)

    # External imports include requests, os, json
    assert "requests" in result.imports_external
    assert "os" in result.imports_external
    assert "json" in result.imports_external

    # No internal imports in hello.py
    assert result.imports_internal == []

    # Triggers: __main__ guard
    assert any(t.type == "cli" and t.detail == "__main__ guard" for t in result.triggers)

    # Signature: main(url, output, verbose)
    assert result.signature is not None
    assert "url" in result.signature
    assert "output" in result.signature
    assert "verbose" in result.signature


def test_hello_steps(hello_script, fixtures_dir):
    result = analyze_file(hello_script, fixtures_dir)
    step_types = {s.type for s in result.steps}

    # Must have api_call (requests.get), file_io (open + json.dump), decision (if verbose), output (print)
    assert "api_call" in step_types
    assert "file_io" in step_types
    assert "decision" in step_types
    assert "output" in step_types

    # Check function scope tracking
    api_steps = [s for s in result.steps if s.type == "api_call"]
    assert any(s.function_name == "fetch_data" for s in api_steps)

    file_steps = [s for s in result.steps if s.type == "file_io"]
    assert any(s.function_name == "save_results" for s in file_steps)


def test_steps_ordered_by_line(hello_script, fixtures_dir):
    result = analyze_file(hello_script, fixtures_dir)
    lines = [s.line_number for s in result.steps]
    assert lines == sorted(lines)


def test_syntax_error_returns_empty(fixtures_dir, tmp_path):
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def oops(:\n  pass")
    result = analyze_file(bad_file, tmp_path)
    assert result.path == "bad.py"
    assert result.steps == []
    assert result.services == []


def test_no_main_no_entry_point(tmp_path):
    script = tmp_path / "helper.py"
    script.write_text("def helper(): return 42\n")
    result = analyze_file(script, tmp_path)
    assert result.is_entry_point is False
    assert result.signature is None


def test_db_operations(tmp_path):
    script = tmp_path / "db.py"
    script.write_text("""
import sqlite3
conn = sqlite3.connect("test.db")
cursor = conn.cursor()
cursor.execute("SELECT * FROM users")
rows = cursor.fetchall()
conn.commit()
""")
    result = analyze_file(script, tmp_path)
    db_steps = [s for s in result.steps if s.type == "db_op"]
    assert len(db_steps) >= 2  # execute + fetchall at minimum


def test_db_op_no_false_positives(tmp_path):
    """Common methods like .add(), .find(), .flush() on non-DB objects must NOT be db_op."""
    script = tmp_path / "nodb.py"
    script.write_text("""
items = set()
items.add("hello")
idx = "abcdef".find("c")
import sys
sys.stdout.flush()
""")
    result = analyze_file(script, tmp_path)
    db_steps = [s for s in result.steps if s.type == "db_op"]
    assert db_steps == [], f"False positive db_op steps: {db_steps}"


def test_logging_output(tmp_path):
    script = tmp_path / "loggy.py"
    script.write_text("""
import logging
logger = logging.getLogger(__name__)
logger.info("starting")
logger.error("something broke")
""")
    result = analyze_file(script, tmp_path)
    output_steps = [s for s in result.steps if s.type == "output"]
    assert len(output_steps) >= 2


def test_internal_import_detection(tmp_path):
    (tmp_path / "utils.py").write_text("def helper(): pass\n")
    script = tmp_path / "main.py"
    script.write_text("from utils import helper\nhelper()\n")
    result = analyze_file(script, tmp_path)
    assert "utils" in result.imports_internal


def test_internal_import_subdirectory(tmp_path):
    """Module in a subdirectory should be classified as internal, not external."""
    subdir = tmp_path / "src"
    subdir.mkdir()
    (subdir / "utils.py").write_text("def helper(): pass\n")
    script = subdir / "main.py"
    script.write_text("from utils import helper\nhelper()\n")
    result = analyze_file(script, tmp_path)
    assert "utils" in result.imports_internal
    assert "utils" not in result.imports_external


def test_multiple_secrets(tmp_path):
    script = tmp_path / "secrets.py"
    script.write_text("""
import os
key = os.getenv("API_KEY")
secret = os.environ.get("SECRET")
token = os.environ["TOKEN"]
""")
    result = analyze_file(script, tmp_path)
    assert set(result.secrets) == {"API_KEY", "SECRET", "TOKEN"}


def test_secrets_decouple_attribute(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("import decouple\nkey = decouple.config('API_KEY')\n")
    result = analyze_file(script, tmp_path)
    assert "API_KEY" in result.secrets


def test_secrets_decouple_import(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("from decouple import config\nkey = config('DB_URL')\n")
    result = analyze_file(script, tmp_path)
    assert "DB_URL" in result.secrets


def test_secrets_decouple_with_default(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("from decouple import config\nport = config('PORT', default='5432')\n")
    result = analyze_file(script, tmp_path)
    assert "PORT" in result.secrets


def test_secrets_decouple_variable_key_not_detected(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("from decouple import config\nkey_name = 'MY_KEY'\nval = config(key_name)\n")
    result = analyze_file(script, tmp_path)
    assert "MY_KEY" not in result.secrets


def test_secrets_config_without_decouple_not_detected(tmp_path):
    script = tmp_path / "s.py"
    script.write_text("val = config('SOME_KEY')\n")
    result = analyze_file(script, tmp_path)
    assert "SOME_KEY" not in result.secrets


# --- Gap 4: file_io false positive tests ---


def test_file_io_pathlib_still_detected(tmp_path):
    script = tmp_path / "pathlib_io.py"
    script.write_text("from pathlib import Path\ndata = Path('f.txt').read_text()\n")
    result = analyze_file(script, tmp_path)
    io_steps = [s for s in result.steps if s.type == "file_io"]
    assert len(io_steps) >= 1


def test_file_io_no_false_positive_on_loads(tmp_path):
    """myobj.loads() on non-module object should NOT be file_io."""
    script = tmp_path / "noio.py"
    script.write_text('result = myobj.loads("data")\n')
    result = analyze_file(script, tmp_path)
    io_steps = [s for s in result.steps if s.type == "file_io"]
    assert io_steps == [], f"False positive file_io: {io_steps}"


def test_json_dump_still_file_io(tmp_path):
    script = tmp_path / "jsonio.py"
    script.write_text("import json\njson.dump(data, f)\n")
    result = analyze_file(script, tmp_path)
    io_steps = [s for s in result.steps if s.type == "file_io"]
    assert len(io_steps) >= 1


# --- Gap 1: transform detection tests ---


def test_transform_list_comprehension(tmp_path):
    script = tmp_path / "comp.py"
    script.write_text("items = [x * 2 for x in range(10)]\n")
    result = analyze_file(script, tmp_path)
    transform_steps = [s for s in result.steps if s.type == "transform"]
    assert len(transform_steps) >= 1
    assert any("list comprehension:" in s.description for s in transform_steps)


def test_transform_dict_comprehension(tmp_path):
    script = tmp_path / "dictcomp.py"
    script.write_text("d = {k: v for k, v in items}\n")
    result = analyze_file(script, tmp_path)
    assert any(s.type == "transform" and "dict comprehension:" in s.description for s in result.steps)


def test_transform_builtins(tmp_path):
    script = tmp_path / "builtins.py"
    script.write_text("x = sorted(items)\ny = len(data)\nz = int(value)\n")
    result = analyze_file(script, tmp_path)
    transform_steps = [s for s in result.steps if s.type == "transform"]
    assert len(transform_steps) >= 3
    descs = {s.description for s in transform_steps}
    assert "sorted()" in descs
    assert "len()" in descs
    assert "int()" in descs


def test_transform_string_methods(tmp_path):
    script = tmp_path / "strops.py"
    script.write_text('x = "hello".upper()\ny = data.split(",")\n')
    result = analyze_file(script, tmp_path)
    transform_steps = [s for s in result.steps if s.type == "transform"]
    assert len(transform_steps) >= 2


def test_transform_loads_on_unknown_obj(tmp_path):
    """.loads() on non-module object should be transform, not file_io."""
    script = tmp_path / "convert.py"
    script.write_text('result = myobj.loads("data")\n')
    result = analyze_file(script, tmp_path)
    transform_steps = [s for s in result.steps if s.type == "transform"]
    assert len(transform_steps) >= 1


# --- Gap 2: inputs/outputs tests ---


def test_io_assignment_outputs(tmp_path):
    """Variable name on left side of = should populate outputs."""
    script = tmp_path / "assign.py"
    script.write_text("items = sorted(data)\n")
    result = analyze_file(script, tmp_path)
    transform_steps = [s for s in result.steps if s.type == "transform"]
    assert len(transform_steps) >= 1
    assert "items" in transform_steps[0].outputs


def test_io_open_read_mode(tmp_path):
    """open('file', 'r') should put file path in inputs."""
    script = tmp_path / "readfile.py"
    script.write_text("f = open('data.csv', 'r')\n")
    result = analyze_file(script, tmp_path)
    io_steps = [s for s in result.steps if s.type == "file_io"]
    assert len(io_steps) >= 1
    assert "data.csv" in io_steps[0].inputs


def test_io_open_write_mode(tmp_path):
    """open('file', 'w') should put file path in outputs."""
    script = tmp_path / "writefile.py"
    script.write_text("f = open('output.json', 'w')\n")
    result = analyze_file(script, tmp_path)
    io_steps = [s for s in result.steps if s.type == "file_io"]
    assert len(io_steps) >= 1
    assert "output.json" in io_steps[0].outputs


def test_io_open_keyword_mode(tmp_path):
    """open('file', mode='w') keyword form should work too."""
    script = tmp_path / "kwmode.py"
    script.write_text("f = open('out.txt', mode='w')\n")
    result = analyze_file(script, tmp_path)
    io_steps = [s for s in result.steps if s.type == "file_io"]
    assert len(io_steps) >= 1
    assert "out.txt" in io_steps[0].outputs


def test_io_decision_inputs(tmp_path):
    """Decision conditions should extract variable names as inputs."""
    script = tmp_path / "branch.py"
    script.write_text("if verbose:\n    print('yes')\n")
    result = analyze_file(script, tmp_path)
    decisions = [s for s in result.steps if s.type == "decision"]
    assert len(decisions) >= 1
    assert "verbose" in decisions[0].inputs


def test_service_attributed_via_last_segment(tmp_path):
    """from google.cloud import storage; storage.Client() should match Google Cloud Storage."""
    script = tmp_path / "s.py"
    script.write_text(
        "from google.cloud import storage\n"
        "client = storage.Client()\n"
        "bucket = client.get_bucket('my-bucket')\n"
    )
    result = analyze_file(script, tmp_path)
    api_steps = [s for s in result.steps if s.type == "api_call" and s.service is not None]
    assert any(s.service and "Cloud Storage" in s.service.name for s in api_steps)


def test_hello_fixture_io(hello_script, fixtures_dir):
    """hello.py should have populated inputs/outputs where determinable."""
    result = analyze_file(hello_script, fixtures_dir)

    # Decision steps should have inputs (variable names from conditions)
    decisions = [s for s in result.steps if s.type == "decision"]
    assert any(s.inputs for s in decisions), f"No decision inputs: {decisions}"

    # Assignment outputs: e.g. `data = fetch_data(url)` should have outputs=["data"]
    api_steps = [s for s in result.steps if s.type == "api_call"]
    # requests.get is inside fetch_data, assigned to `response`
    assert any(s.outputs for s in api_steps), f"No API call outputs: {api_steps}"
