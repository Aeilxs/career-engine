import sqlite3
from pathlib import Path

import pytest

from career_engine.cli import main
from career_engine.db import SCHEMA_VERSION, initialize, read_marker, write_marker


def test_marker_persists_between_connections(tmp_path: Path) -> None:
    path = tmp_path / "career.db"
    initialize(path)
    write_marker("J0-persistent", path)
    initialize(path)
    assert read_marker(path) == "J0-persistent"
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_marker_invalid_value_does_not_mutate(tmp_path: Path) -> None:
    path = tmp_path / "career.db"
    initialize(path)
    with pytest.raises(ValueError):
        write_marker("", path)
    assert read_marker(path) is None


def test_doctor_uses_isolated_dir(isolated_data: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["doctor"]) == 0
    assert '"ok": true' in capsys.readouterr().out
    assert (isolated_data / "career.db").is_file()


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["--version"])
    assert error.value.code == 0
    assert "0.1.0" in capsys.readouterr().out


def test_newer_schema_rejected(tmp_path: Path) -> None:
    path = tmp_path / "newer.db"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="Unsupported schema version"):
        initialize(path)
