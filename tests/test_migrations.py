"""Schema migrations: fresh and upgrade paths, immutability enforced by the database."""

import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest

from career_engine.db import (
    MIGRATIONS,
    SCHEMA_VERSION,
    _split_statements,
    connect,
    initialize,
    read_marker,
    write_marker,
)

J1_TABLES = {
    "source_snapshot",
    "offer",
    "offer_revision",
    "duplicate_suggestion",
    "application",
    "application_event",
    "job",
}


def _tables(path: Path) -> set[str]:
    with closing(connect(path)) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def test_fresh_database_reaches_current_schema(tmp_path: Path) -> None:
    path = tmp_path / "career.db"
    initialize(path)
    assert J1_TABLES <= _tables(path)
    with closing(connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION >= 2
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    initialize(path)  # idempotent


def test_upgrade_from_j0_schema_preserves_marker(tmp_path: Path) -> None:
    path = tmp_path / "career.db"
    with closing(sqlite3.connect(path)) as legacy:
        for statement in _split_statements(MIGRATIONS[1]):
            legacy.execute(statement)
        legacy.execute("INSERT INTO bootstrap_marker (id, value) VALUES (1, 'from-j0')")
        legacy.execute("PRAGMA user_version = 1")
        legacy.commit()
    assert not J1_TABLES & _tables(path)
    initialize(path)
    assert J1_TABLES <= _tables(path)
    assert read_marker(path) == "from-j0"


def test_upgrade_from_v2_backfills_acquisition_provenance(tmp_path: Path) -> None:
    path = tmp_path / "career.db"
    with closing(sqlite3.connect(path)) as legacy:
        for version in (1, 2):
            for statement in _split_statements(MIGRATIONS[version]):
                legacy.execute(statement)
            legacy.execute(f"PRAGMA user_version = {version}")
        legacy.execute("INSERT INTO bootstrap_marker (id, value) VALUES (1, 'from-j0')")
        legacy.execute(
            "INSERT INTO source_snapshot (id, source_ref, retrieved_at, mime, content_sha256, "
            "size_bytes, connector_version, object_ref) "
            "VALUES ('snapshot', 'legacy-source', '2026-01-01T00:00:00+00:00', "
            "'text/plain', ?, 1, 'manual-text-1', 'objects/legacy')",
            ("a" * 64,),
        )
        legacy.execute(
            "INSERT INTO offer (id, provider, board, external_id, identity_kind, created_at) "
            "VALUES ('offer', 'provider-a', 'board-a', 'source-a', 'native', 'created')"
        )
        legacy.execute(
            "INSERT INTO offer_revision (id, offer_id, revision_number, snapshot_id, "
            "provenance_json, normalized_sha256, created_at) "
            "VALUES ('revision', 'offer', 1, 'snapshot', '{}', ?, 'created')",
            ("b" * 64,),
        )
        legacy.execute("PRAGMA user_version = 2")
        legacy.commit()

    initialize(path)

    with closing(connect(path)) as connection:
        acquisition = connection.execute("SELECT * FROM source_acquisition").fetchone()
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
    assert read_marker(path) == "from-j0"
    assert dict(acquisition) == {
        "id": "revision",
        "snapshot_id": "snapshot",
        "offer_revision_id": "revision",
        "source_ref": "legacy-source",
        "source_id": "source-a",
        "provider": "provider-a",
        "board": "board-a",
        "retrieved_at": "2026-01-01T00:00:00+00:00",
    }


def test_concurrent_initialization_is_safe(tmp_path: Path) -> None:
    for repetition in range(20):
        path = tmp_path / f"career-{repetition}.db"
        barrier = threading.Barrier(6, timeout=10)
        errors: list[BaseException] = []

        def run(
            barrier: threading.Barrier = barrier,
            path: Path = path,
            errors: list[BaseException] = errors,
        ) -> None:
            try:
                barrier.wait()
                initialize(path)
            except BaseException as error:
                errors.append(error)

        threads = [threading.Thread(target=run, daemon=True) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)
        assert all(not thread.is_alive() for thread in threads)
        assert errors == []
        write_marker(f"round-{repetition}", path)
        initialize(path)
        assert read_marker(path) == f"round-{repetition}"
        assert J1_TABLES <= _tables(path)
        with closing(connect(path)) as connection:
            assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


def test_failed_migration_rolls_back_completely(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "career.db"
    initialize(path)
    broken = {**MIGRATIONS, SCHEMA_VERSION + 1: "CREATE TABLE half_done (id INTEGER);\nBROKEN SQL;"}
    monkeypatch.setattr("career_engine.db.MIGRATIONS", broken)
    monkeypatch.setattr("career_engine.db.SCHEMA_VERSION", SCHEMA_VERSION + 1)
    with pytest.raises(sqlite3.Error):
        initialize(path)
    assert "half_done" not in _tables(path)
    with closing(connect(path)) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE source_snapshot SET source_ref = 'x'",
        "DELETE FROM source_snapshot",
        "UPDATE offer_revision SET title = 'x'",
        "DELETE FROM offer_revision",
        "UPDATE application_event SET reason = 'x'",
        "DELETE FROM application_event",
        "UPDATE source_acquisition SET source_ref = 'x'",
        "DELETE FROM source_acquisition",
    ],
)
def test_evidence_tables_are_immutable(tmp_path: Path, statement: str) -> None:
    path = tmp_path / "career.db"
    initialize(path)
    with closing(connect(path)) as connection:
        with connection:
            connection.execute(
                "INSERT INTO source_snapshot (id, source_ref, retrieved_at, mime, "
                "content_sha256, size_bytes, connector_version, object_ref) "
                "VALUES ('s', 'r', 't', 'text/plain', ?, 1, 'v', 'o')",
                ("a" * 64,),
            )
            connection.execute(
                "INSERT INTO offer (id, provider, board, external_id, identity_kind, created_at) "
                "VALUES ('o', 'p', '', 'e', 'native', 't')"
            )
            connection.execute(
                "INSERT INTO offer_revision (id, offer_id, revision_number, snapshot_id, "
                "provenance_json, normalized_sha256, created_at) "
                "VALUES ('r', 'o', 1, 's', '{}', ?, 't')",
                ("b" * 64,),
            )
            connection.execute(
                "INSERT INTO source_acquisition (id, snapshot_id, offer_revision_id, source_ref, "
                "source_id, provider, board, retrieved_at) "
                "VALUES ('x', 's', 'r', 'ref', 'source', 'provider', 'board', 't')"
            )
            connection.execute(
                "INSERT INTO application (id, offer_id, offer_revision_id, stage, version, "
                "dossier_path, manifest_sha256, created_at, updated_at) "
                "VALUES ('a', 'o', 'r', 'DRAFT', 1, 'd', ?, 't', 't')",
                ("c" * 64,),
            )
            connection.execute(
                "INSERT INTO application_event (id, application_id, kind, to_stage, actor, "
                "reason, resulting_version, created_at) "
                "VALUES ('e', 'a', 'CREATED', 'DRAFT', 'u', 'r', 1, 't')"
            )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(statement)
