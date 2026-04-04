"""Integration tests — full pipeline on real fixture scripts."""

import pytest

from visualpy.analyzer.cross_file import resolve_connections
from visualpy.analyzer.scanner import scan_project


@pytest.fixture
def agentic_results(fixtures_dir):
    """Run full analysis pipeline on agentic_workflows fixtures."""
    path = fixtures_dir / "agentic_workflows"
    scripts = scan_project(path)
    connections = resolve_connections(scripts, path)
    return scripts, connections


class TestAgenticWorkflows:
    """Integration tests using the 8 real agentic workflow scripts."""

    def test_all_scripts_found(self, agentic_results):
        scripts, _ = agentic_results
        assert len(scripts) == 10

    def test_services_detected(self, agentic_results):
        scripts, _ = agentic_results
        all_services = set()
        for s in scripts:
            for svc in s.services:
                all_services.add(svc.name)

        # These scripts use Google Sheets, HTTP Client, OpenAI, etc.
        assert "Google Sheets" in all_services or "Google Auth" in all_services
        assert "HTTP Client" in all_services

    def test_secrets_detected(self, agentic_results):
        scripts, _ = agentic_results
        all_secrets = set()
        for s in scripts:
            all_secrets.update(s.secrets)

        # Various env vars across the fixture scripts
        assert len(all_secrets) > 0

    def test_entry_points_detected(self, agentic_results):
        scripts, _ = agentic_results
        entry_points = [s.path for s in scripts if s.is_entry_point]
        assert len(entry_points) > 0

    def test_import_connections_found(self, agentic_results):
        _, connections = agentic_results
        import_conns = [c for c in connections if c.type == "import"]
        # gmaps_lead_pipeline.py imports scrape_google_maps
        assert any(
            "gmaps_lead_pipeline" in c.source and "scrape_google_maps" in c.target
            for c in import_conns
        )

    def test_steps_extracted(self, agentic_results):
        scripts, _ = agentic_results
        total_steps = sum(len(s.steps) for s in scripts)
        # 8 real scripts should produce a healthy number of steps
        assert total_steps > 20

    def test_triggers_detected(self, agentic_results):
        scripts, _ = agentic_results
        all_triggers = []
        for s in scripts:
            all_triggers.extend(s.triggers)
        # At least some scripts have __main__ guards or argparse
        assert len(all_triggers) > 0

    def test_each_script_has_steps(self, agentic_results):
        scripts, _ = agentic_results
        for script in scripts:
            assert len(script.steps) > 0, f"{script.path} has no steps"


class TestHelloFixture:
    """Integration tests using the minimal hello.py fixture."""

    def test_full_pipeline(self, hello_script, fixtures_dir):
        scripts = scan_project(hello_script)
        assert len(scripts) == 1

        script = scripts[0]
        assert script.is_entry_point is True
        assert "MY_API_KEY" in script.secrets
        assert any(s.name == "HTTP Client" for s in script.services)
        assert script.signature is not None
        assert len(script.steps) >= 4  # api_call, file_io, decision, output

        step_types = {s.type for s in script.steps}
        assert "api_call" in step_types
        assert "file_io" in step_types
        assert "decision" in step_types
        assert "output" in step_types
