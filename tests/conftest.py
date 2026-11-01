"""Tests operate on a temporary directory and never touch ./data."""

from pathlib import Path

import pytest


@pytest.fixture
def isolated_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("CAREER_DATA_DIR", str(tmp_path))
    return tmp_path
