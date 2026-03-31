"""Tests for service_map module."""

from visualpy.analyzer.service_map import SERVICE_MAP, detect_services


def test_simple_match():
    services = detect_services(["requests"])
    assert len(services) == 1
    assert services[0].name == "HTTP Client"
    assert services[0].library == "requests"


def test_prefix_match():
    services = detect_services(["google.oauth2.credentials"])
    assert len(services) == 1
    assert services[0].name == "Google Auth"


def test_longest_prefix_wins():
    services = detect_services(["google.cloud.storage.blob"])
    assert len(services) == 1
    assert services[0].name == "Google Cloud Storage"


def test_multiple_imports():
    services = detect_services(["openai", "gspread", "requests"])
    names = {s.name for s in services}
    assert names == {"OpenAI", "Google Sheets", "HTTP Client"}


def test_deduplication():
    services = detect_services(["requests", "requests.auth"])
    assert len(services) == 1
    assert services[0].name == "HTTP Client"


def test_unknown_import_ignored():
    services = detect_services(["my_custom_lib", "pathlib", "os"])
    assert services == []


def test_empty_imports():
    assert detect_services([]) == []


def test_service_map_has_minimum_entries():
    assert len(SERVICE_MAP) >= 20
