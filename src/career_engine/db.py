"""Minimal SQLite persistence for J0; no domain schema is invented here."""

import sqlite3
from contextlib import closing
from pathlib import Path

from career_engine.config import database_path

SCHEMA_VERSION = 1


def connect(path: Path | None = None) -> sqlite3.Connection:
    resolved = path if path is not None else database_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialize(path: Path | None = None) -> None:
    with closing(connect(path)) as connection:
        with connection:
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current > SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported schema version: {current}")
            if current == 0:
                # Schema creation and version bump must commit atomically.
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE bootstrap_marker ("
                    "id INTEGER PRIMARY KEY CHECK(id = 1), "
                    "value TEXT NOT NULL CHECK(length(value) <= 128))"
                )
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def read_marker(path: Path | None = None) -> str | None:
    with closing(connect(path)) as connection:
        row = connection.execute("SELECT value FROM bootstrap_marker WHERE id = 1").fetchone()
    return None if row is None else str(row["value"])


def write_marker(value: str, path: Path | None = None) -> None:
    if not value or len(value) > 128:
        raise ValueError("Marker must be 1 to 128 characters long")
    with closing(connect(path)) as connection:
        with connection:
            connection.execute(
                "INSERT INTO bootstrap_marker (id, value) VALUES (1, ?) "
                "ON CONFLICT(id) DO UPDATE SET value=excluded.value",
                (value,),
            )
