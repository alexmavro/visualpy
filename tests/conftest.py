"""Shared test fixtures for visualpy."""

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Path to test fixture files."""
    return FIXTURES_DIR


@pytest.fixture
def hello_script(fixtures_dir):
    """Path to the minimal hello.py fixture."""
    return fixtures_dir / "hello.py"
