"""Application use cases. An application is a separate record from the offer it refers to."""

import json
import shutil
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

from career_engine.clock import now_iso
from career_engine.config import database_path_for
from career_engine.db import connect, write_transaction
from career_engine.domain.applications import INITIAL_STAGE, check_transition
from career_engine.domain.errors import Conflict, NotFound, ValidationFailed
from career_engine.infrastructure.objects import atomic_write_bytes, sha256_hex

MANIFEST_SCHEMA_VERSION = 1
MAX_REASON_CHARS = 500
DEFAULT_ACTOR = "local-user"


def dossier_relative_path(application_id: str) -> str:
    return f"applications/{application_id}"


def manifest_relative_path(application_id: str) -> str:
    return f"{dossier_relative_path(application_id)}/manifest.json"


def _clean_actor(actor: str) -> str:
    cleaned = actor.strip()
    if not cleaned or len(cleaned) > 100 or any(ord(char) < 32 for char in cleaned):
        raise ValidationFailed("Invalid actor.", "INVALID_ACTOR")
    return cleaned


def create_application(
    data_dir: Path, offer_id: str, *, actor: str = DEFAULT_ACTOR
) -> dict[str, Any]:
    """Create the application, its hashed manifest folder and its first history event.

    The manifest is written atomically before the SQL commit. If the commit fails, the folder
    (which carries a brand-new UUID) is removed again so no half-created application remains.
    """
    actor = _clean_actor(actor)
    database = database_path_for(data_dir)
    with closing(connect(database)) as connection:
        source = connection.execute(
            "SELECT o.id AS offer_id, r.id AS revision_id, r.revision_number, "
            "r.normalized_sha256, s.id AS snapshot_id, s.content_sha256, s.object_ref "
            "FROM offer o JOIN offer_revision r ON r.id = o.current_revision_id "
            "JOIN source_snapshot s ON s.id = r.snapshot_id WHERE o.id = ?",
            (offer_id,),
        ).fetchone()
        if source is None:
            raise NotFound("Offer not found.")
        if connection.execute(
            "SELECT 1 FROM application WHERE offer_id = ?", (offer_id,)
        ).fetchone():
            raise Conflict("An application already exists for this offer.", "APPLICATION_EXISTS")

    application_id = str(uuid.uuid4())
    now = now_iso()
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "application_id": application_id,
        "offer_id": offer_id,
        "offer_revision_id": source["revision_id"],
        "offer_revision_number": source["revision_number"],
        "offer_normalized_sha256": source["normalized_sha256"],
        "source_snapshot_id": source["snapshot_id"],
        "source_content_sha256": source["content_sha256"],
        "source_object_ref": source["object_ref"],
        "created_at": now,
    }
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    manifest_sha256 = sha256_hex(manifest_bytes)
    atomic_write_bytes(data_dir / manifest_relative_path(application_id), manifest_bytes)
    try:
        with closing(connect(database)) as connection:
            with write_transaction(connection):
                connection.execute(
                    "INSERT INTO application (id, offer_id, offer_revision_id, stage, version, "
                    "dossier_path, manifest_sha256, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?)",
                    (
                        application_id,
                        offer_id,
                        source["revision_id"],
                        INITIAL_STAGE,
                        dossier_relative_path(application_id),
                        manifest_sha256,
                        now,
                        now,
                    ),
                )
                connection.execute(
                    "INSERT INTO application_event (id, application_id, kind, from_stage, "
                    "to_stage, actor, reason, resulting_version, created_at) "
                    "VALUES (?, ?, 'CREATED', NULL, ?, ?, 'Application created from offer', 1, ?)",
                    (str(uuid.uuid4()), application_id, INITIAL_STAGE, actor, now),
                )
    except BaseException as error:
        shutil.rmtree(data_dir / dossier_relative_path(application_id), ignore_errors=True)
        if isinstance(error, sqlite3.IntegrityError) and "application.offer_id" in str(error):
            raise Conflict(
                "An application already exists for this offer.", "APPLICATION_EXISTS"
            ) from error
        raise
    return get_application(data_dir, application_id)


def transition_application(
    data_dir: Path,
    application_id: str,
    to_stage: str,
    reason: str,
    expected_version: int,
    *,
    actor: str = DEFAULT_ACTOR,
) -> dict[str, Any]:
    """Change the stage and write the history event in one transaction (REQ-017)."""
    actor = _clean_actor(actor)
    reason = reason.strip()
    if not reason or len(reason) > MAX_REASON_CHARS:
        raise ValidationFailed(
            f"A reason of 1 to {MAX_REASON_CHARS} characters is required.", "INVALID_REASON"
        )
    now = now_iso()
    with closing(connect(database_path_for(data_dir))) as connection:
        with write_transaction(connection):
            row = connection.execute(
                "SELECT stage, version FROM application WHERE id = ?", (application_id,)
            ).fetchone()
            if row is None:
                raise NotFound("Application not found.")
            if int(row["version"]) != expected_version:
                raise Conflict(
                    f"Stale version: expected {expected_version}, current {row['version']}.",
                    "VERSION_CONFLICT",
                )
            check_transition(str(row["stage"]), to_stage)
            new_version = expected_version + 1
            connection.execute(
                "INSERT INTO application_event (id, application_id, kind, from_stage, to_stage, "
                "actor, reason, resulting_version, created_at) "
                "VALUES (?, ?, 'STAGE_CHANGED', ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid.uuid4()),
                    application_id,
                    row["stage"],
                    to_stage,
                    actor,
                    reason,
                    new_version,
                    now,
                ),
            )
            updated = connection.execute(
                "UPDATE application SET stage = ?, version = ?, updated_at = ? "
                "WHERE id = ? AND version = ?",
                (to_stage, new_version, now, application_id, expected_version),
            )
            if updated.rowcount != 1:
                raise Conflict("Concurrent update detected.", "VERSION_CONFLICT")
    return get_application(data_dir, application_id)


_APPLICATION_COLUMNS = (
    "a.id, a.offer_id, a.offer_revision_id, a.stage, a.recruiter_status, a.version, "
    "a.dossier_path, a.manifest_sha256, a.created_at, a.updated_at, "
    "r.revision_number AS offer_revision_number, r.title, r.company, "
    "(SELECT cur.revision_number FROM offer o JOIN offer_revision cur "
    " ON cur.id = o.current_revision_id WHERE o.id = a.offer_id) AS current_offer_revision_number"
)


def list_applications(data_dir: Path) -> list[dict[str, Any]]:
    with closing(connect(database_path_for(data_dir))) as connection:
        rows = connection.execute(
            f"SELECT {_APPLICATION_COLUMNS} FROM application a "
            "JOIN offer_revision r ON r.id = a.offer_revision_id "
            "ORDER BY a.created_at DESC, a.rowid DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_application(data_dir: Path, application_id: str) -> dict[str, Any]:
    with closing(connect(database_path_for(data_dir))) as connection:
        row = connection.execute(
            f"SELECT {_APPLICATION_COLUMNS} FROM application a "
            "JOIN offer_revision r ON r.id = a.offer_revision_id WHERE a.id = ?",
            (application_id,),
        ).fetchone()
        if row is None:
            raise NotFound("Application not found.")
        events = connection.execute(
            "SELECT id, kind, from_stage, to_stage, actor, reason, resulting_version, created_at "
            "FROM application_event WHERE application_id = ? ORDER BY rowid",
            (application_id,),
        ).fetchall()
    return {**dict(row), "events": [dict(event) for event in events]}
