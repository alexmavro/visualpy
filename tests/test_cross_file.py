"""Tests for cross_file module."""

from pathlib import Path

from visualpy.analyzer.cross_file import resolve_connections
from visualpy.analyzer.scanner import scan_project


def test_import_connection_in_agentic_workflows(fixtures_dir):
    scripts = scan_project(fixtures_dir / "agentic_workflows")
    connections = resolve_connections(scripts, fixtures_dir / "agentic_workflows")

    # gmaps_lead_pipeline.py imports from scrape_google_maps.py
    import_conns = [c for c in connections if c.type == "import"]
    assert any(
        c.source == "gmaps_lead_pipeline.py" and c.target == "scrape_google_maps.py"
        for c in import_conns
    ), f"Expected import connection, got: {import_conns}"


def test_import_connection_synthetic(tmp_path):
    (tmp_path / "utils.py").write_text("def helper(): pass\n")
    (tmp_path / "main.py").write_text("from utils import helper\nhelper()\n")

    scripts = scan_project(tmp_path)
    connections = resolve_connections(scripts, tmp_path)

    import_conns = [c for c in connections if c.type == "import"]
    assert len(import_conns) == 1
    assert import_conns[0].source == "main.py"
    assert import_conns[0].target == "utils.py"


def test_file_io_connection(tmp_path):
    (tmp_path / "writer.py").write_text("f = open('data.csv', 'w')\n")
    (tmp_path / "reader.py").write_text("f = open('data.csv', 'r')\n")

    scripts = scan_project(tmp_path)
    connections = resolve_connections(scripts, tmp_path)

    io_conns = [c for c in connections if c.type == "file_io"]
    assert len(io_conns) == 1
    assert "data.csv" in io_conns[0].detail


def test_no_self_connections(tmp_path):
    (tmp_path / "solo.py").write_text("x = 1\n")
    scripts = scan_project(tmp_path)
    connections = resolve_connections(scripts, tmp_path)
    assert all(c.source != c.target for c in connections)


def test_empty_scripts():
    connections = resolve_connections([], Path("/tmp"))
    assert connections == []


def test_file_io_connection_via_structured_io(tmp_path):
    """Cross-file should detect shared files via step.inputs/outputs, not just descriptions."""
    (tmp_path / "writer.py").write_text("f = open('shared.csv', 'w')\n")
    (tmp_path / "reader.py").write_text("f = open('shared.csv', 'r')\n")

    scripts = scan_project(tmp_path)
    connections = resolve_connections(scripts, tmp_path)

    io_conns = [c for c in connections if c.type == "file_io"]
    assert len(io_conns) == 1
    assert "shared.csv" in io_conns[0].detail


def test_file_io_connection_direction(tmp_path):
    """Writer is the source, reader is the target — not reversed."""
    (tmp_path / "writer.py").write_text("f = open('out.csv', 'w')\n")
    (tmp_path / "reader.py").write_text("f = open('out.csv', 'r')\n")

    scripts = scan_project(tmp_path)
    connections = resolve_connections(scripts, tmp_path)

    io_conns = [c for c in connections if c.type == "file_io"]
    assert len(io_conns) == 1
    assert io_conns[0].source.endswith("writer.py")
    assert io_conns[0].target.endswith("reader.py")


def test_file_io_no_connection_when_both_only_read(tmp_path):
    """Two readers of the same file produce no connection — nobody writes it."""
    (tmp_path / "reader_a.py").write_text("f = open('shared.csv', 'r')\n")
    (tmp_path / "reader_b.py").write_text("f = open('shared.csv', 'r')\n")

    scripts = scan_project(tmp_path)
    connections = resolve_connections(scripts, tmp_path)

    assert not any(c.type == "file_io" for c in connections)


def test_deduplication(tmp_path):
    (tmp_path / "utils.py").write_text("def a(): pass\ndef b(): pass\n")
    (tmp_path / "main.py").write_text("from utils import a\nfrom utils import b\n")

    scripts = scan_project(tmp_path)
    connections = resolve_connections(scripts, tmp_path)

    import_conns = [c for c in connections if c.type == "import"]
    # Should be deduplicated to 1 connection despite 2 imports from same file
    assert len(import_conns) == 1
