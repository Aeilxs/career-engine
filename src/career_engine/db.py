"""SQLite persistence: connection policy and explicit, ordered schema migrations."""

import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from career_engine.config import database_path

_MIGRATION_1_BOOTSTRAP = """
CREATE TABLE bootstrap_marker (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    value TEXT NOT NULL CHECK(length(value) <= 128)
);
"""

# J1: offers, immutable source evidence, applications, transitions, duplicate suggestions, jobs.
_MIGRATION_2_J1 = """
CREATE TABLE source_snapshot (
    id TEXT PRIMARY KEY,
    source_ref TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    mime TEXT NOT NULL,
    http_status INTEGER,
    error_code TEXT,
    content_sha256 TEXT NOT NULL UNIQUE CHECK(length(content_sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    connector_version TEXT NOT NULL,
    object_ref TEXT NOT NULL
);

CREATE TABLE offer (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    board TEXT NOT NULL,
    external_id TEXT NOT NULL,
    identity_kind TEXT NOT NULL CHECK(identity_kind IN ('native', 'url', 'content')),
    canonical_url TEXT,
    current_revision_id TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(provider, board, external_id)
);

CREATE TABLE offer_revision (
    id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL REFERENCES offer(id),
    revision_number INTEGER NOT NULL CHECK(revision_number >= 1),
    snapshot_id TEXT NOT NULL REFERENCES source_snapshot(id),
    title TEXT,
    company TEXT,
    locations_json TEXT,
    contract TEXT,
    salary_raw_text TEXT,
    description TEXT,
    apply_url TEXT,
    provenance_json TEXT NOT NULL,
    normalized_sha256 TEXT NOT NULL CHECK(length(normalized_sha256) = 64),
    created_at TEXT NOT NULL,
    UNIQUE(offer_id, revision_number)
);

CREATE TABLE duplicate_suggestion (
    id TEXT PRIMARY KEY,
    offer_a_id TEXT NOT NULL REFERENCES offer(id),
    offer_b_id TEXT NOT NULL REFERENCES offer(id),
    score REAL NOT NULL CHECK(score >= 0 AND score <= 1),
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('SUGGESTED')),
    created_at TEXT NOT NULL,
    CHECK(offer_a_id < offer_b_id),
    UNIQUE(offer_a_id, offer_b_id)
);

CREATE TABLE application (
    id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL UNIQUE REFERENCES offer(id),
    offer_revision_id TEXT NOT NULL REFERENCES offer_revision(id),
    candidate_profile_id TEXT,
    stage TEXT NOT NULL CHECK(stage IN (
        'DRAFT', 'PREPARING', 'REVIEW_REQUIRED', 'APPROVED', 'BLOCKED',
        'SUBMITTING', 'SUBMITTED', 'SUBMISSION_UNKNOWN', 'REJECTED_CERTAIN',
        'NOT_SUBMITTED_CERTAIN'
    )),
    recruiter_status TEXT,
    version INTEGER NOT NULL CHECK(version >= 1),
    dossier_path TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256) = 64),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE application_event (
    id TEXT PRIMARY KEY,
    application_id TEXT NOT NULL REFERENCES application(id),
    kind TEXT NOT NULL CHECK(kind IN ('CREATED', 'STAGE_CHANGED')),
    from_stage TEXT,
    to_stage TEXT NOT NULL,
    actor TEXT NOT NULL CHECK(length(actor) > 0),
    reason TEXT NOT NULL CHECK(length(reason) > 0),
    resulting_version INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX application_event_by_application ON application_event(application_id);

CREATE TABLE job (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'BLOCKED')),
    generation INTEGER NOT NULL DEFAULT 0,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL CHECK(max_attempts >= 1),
    lease_expires_at TEXT,
    result_json TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(kind, input_hash)
);

CREATE TRIGGER source_snapshot_immutable_update BEFORE UPDATE ON source_snapshot
BEGIN SELECT RAISE(ABORT, 'source_snapshot rows are immutable'); END;
CREATE TRIGGER source_snapshot_immutable_delete BEFORE DELETE ON source_snapshot
BEGIN SELECT RAISE(ABORT, 'source_snapshot rows are immutable'); END;
CREATE TRIGGER offer_revision_immutable_update BEFORE UPDATE ON offer_revision
BEGIN SELECT RAISE(ABORT, 'offer_revision rows are immutable'); END;
CREATE TRIGGER offer_revision_immutable_delete BEFORE DELETE ON offer_revision
BEGIN SELECT RAISE(ABORT, 'offer_revision rows are immutable'); END;
CREATE TRIGGER application_event_immutable_update BEFORE UPDATE ON application_event
BEGIN SELECT RAISE(ABORT, 'application_event rows are immutable'); END;
CREATE TRIGGER application_event_immutable_delete BEFORE DELETE ON application_event
BEGIN SELECT RAISE(ABORT, 'application_event rows are immutable'); END;
"""

MIGRATIONS: dict[int, str] = {1: _MIGRATION_1_BOOTSTRAP, 2: _MIGRATION_2_J1}
SCHEMA_VERSION = max(MIGRATIONS)


def connect(path: Path | None = None) -> sqlite3.Connection:
    resolved = path if path is not None else database_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(resolved, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


@contextmanager
def write_transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Short write unit of work: takes the write lock up front, commits or rolls back fully."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    connection.commit()


def initialize(path: Path | None = None) -> None:
    with closing(connect(path)) as connection:
        # The version is read under the write lock so concurrent starters cannot both migrate.
        with write_transaction(connection):
            current = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if current > SCHEMA_VERSION:
                raise RuntimeError(f"Unsupported schema version: {current}")
            for version in range(current + 1, SCHEMA_VERSION + 1):
                for statement in _split_statements(MIGRATIONS[version]):
                    connection.execute(statement)
                connection.execute(f"PRAGMA user_version = {version}")


def _split_statements(script: str) -> Iterator[str]:
    """Split a migration script into statements (triggers contain inner semicolons)."""
    buffer: list[str] = []
    for line in script.splitlines():
        buffer.append(line)
        candidate = "\n".join(buffer).strip()
        if candidate and sqlite3.complete_statement(candidate):
            yield candidate
            buffer = []
    if "\n".join(buffer).strip():
        raise RuntimeError("Migration script ends with an incomplete statement")


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
