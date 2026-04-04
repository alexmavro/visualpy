"""Tests for scanner module."""

from pathlib import Path

from visualpy.analyzer.scanner import scan_project


def test_scan_agentic_workflows(fixtures_dir):
    scripts = scan_project(fixtures_dir / "agentic_workflows")
    assert len(scripts) == 10
    paths = {s.path for s in scripts}
    assert "read_sheet.py" in paths
    assert "scrape_google_maps.py" in paths
    assert "gmaps_lead_pipeline.py" in paths


def test_scan_single_file(hello_script):
    scripts = scan_project(hello_script)
    assert len(scripts) == 1
    assert scripts[0].path == "hello.py"


def test_scan_nonexistent_path(tmp_path):
    scripts = scan_project(tmp_path / "does_not_exist")
    assert scripts == []


def test_scan_empty_dir(tmp_path):
    scripts = scan_project(tmp_path)
    assert scripts == []


def test_skips_pycache(tmp_path):
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "cached.py").write_text("x = 1")
    (tmp_path / "real.py").write_text("x = 1")
    scripts = scan_project(tmp_path)
    assert len(scripts) == 1
    assert scripts[0].path == "real.py"


def test_skips_empty_init(tmp_path):
    (tmp_path / "__init__.py").write_text("")
    (tmp_path / "module.py").write_text("x = 1")
    scripts = scan_project(tmp_path)
    assert len(scripts) == 1
    assert scripts[0].path == "module.py"


def test_sorted_by_path(fixtures_dir):
    scripts = scan_project(fixtures_dir / "agentic_workflows")
    paths = [s.path for s in scripts]
    assert paths == sorted(paths)
