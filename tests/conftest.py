import logging
from pathlib import Path

import pytest

from pcdigitizer import enable_logging

TEST_DIR: Path = Path(__file__).resolve().parent
TMP_DIR: Path = TEST_DIR / "tmp"


@pytest.fixture(scope="session", autouse=True)
def turn_on_logging() -> None:
    """Enable loguru logging at DEBUG level for the entire test session."""
    enable_logging(logging.DEBUG)


@pytest.fixture
def test_dir() -> Path:
    """Return the absolute path to the tests/ directory."""
    return TEST_DIR


@pytest.fixture
def tmp_dir() -> Path:
    """Return the path to the shared temporary output directory."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    return TMP_DIR


@pytest.fixture
def mock_session(test_dir):
    """A fake requests.Session that returns saved fixture files."""

    class FakeResponse:
        def __init__(self, content: bytes, status_code: int = 200):
            self.content = content
            self.status_code = status_code

    class FakeSession:
        def get(self, url):
            if "heading/Dissociation" in url:
                fixture = test_dir / "files" / "dissociation-constants-1.json"
                return FakeResponse(fixture.read_bytes())
            return FakeResponse(b'{"Fault": "not found"}', status_code=404)

    return FakeSession()
