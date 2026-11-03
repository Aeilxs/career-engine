"""Offer ingestion use cases: immutable snapshot + normalized revision, never an application."""

import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from career_engine.clock import now_iso
from career_engine.config import database_path_for
from career_engine.db import connect, write_transaction
from career_engine.domain.errors import NotFound, ValidationFailed
from career_engine.domain.offers import (
    CONNECTOR_VERSION,
    PROVENANCE_SCHEMA_VERSION,
    OfferIdentity,
    canonicalize_url,
    decode_posting,
    derive_identity,
    normalize_posting,
    suggest_duplicate,
)
from career_engine.infrastructure.objects import ObjectStore

MAX_LABEL_CHARS = 500
DEFAULT_SOURCE_REF = "manual-import"


@dataclass(frozen=True)
class ImportResult:
    outcome: str  # created | revision_created | unchanged
    offer_id: str
    revision_id: str
    revision_number: int
    snapshot_id: str
    content_sha256: str
    object_ref: str
    identity: dict[str, str]
    duplicate_suggestions: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _label(value: str | None, name: str) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    if len(cleaned) > MAX_LABEL_CHARS or any(ord(char) < 32 for char in cleaned):
        raise ValidationFailed(f"Invalid {name}.", "INVALID_METADATA")
    return cleaned


def import_posting(
    data_dir: Path,
    raw: bytes,
    *,
    source_ref: str | None = None,
    source_id: str | None = None,
    provider: str | None = None,
    board: str | None = None,
) -> ImportResult:
    """Persist raw bytes as evidence, then offer/revision rows in one SQL transaction.

    Validation happens before anything is written. The object file is written (atomically)
    before the SQL commit; a crash in between leaves only an unreferenced content-addressed
    object, reported by `verify_integrity`, never a half-written offer.
    """
    text = decode_posting(raw)
    label = _label(source_ref, "source reference") or DEFAULT_SOURCE_REF
    normalized = normalize_posting(text)
    digest, object_ref = ObjectStore(data_dir).put(raw)
    identity = derive_identity(
        normalized,
        digest,
        source_id=_label(source_id, "source ID"),
        provider=_label(provider, "provider"),
        board=_label(board, "board"),
    )
    now = now_iso()
    with closing(connect(database_path_for(data_dir))) as connection:
        with write_transaction(connection):
            offer = connection.execute(
                "SELECT id, current_revision_id FROM offer "
                "WHERE provider = ? AND board = ? AND external_id = ?",
                (identity.provider, identity.board, identity.external_id),
            ).fetchone()
            if offer is None:
                offer_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO offer (id, provider, board, external_id, identity_kind, "
                    "created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (offer_id, *_identity_values(identity), now),
                )
                outcome, number = "created", 1
            else:
                offer_id = str(offer["id"])
                current = connection.execute(
                    "SELECT r.id, r.revision_number, s.id AS snapshot_id "
                    "FROM offer_revision r JOIN source_snapshot s ON s.id = r.snapshot_id "
                    "WHERE r.id = ? AND s.content_sha256 = ?",
                    (offer["current_revision_id"], digest),
                ).fetchone()
                if current is not None:
                    _record_acquisition(
                        connection,
                        snapshot_id=str(current["snapshot_id"]),
                        revision_id=str(current["id"]),
                        source_ref=label,
                        source_id=identity.external_id,
                        provider=identity.provider,
                        board=identity.board,
                        retrieved_at=now,
                    )
                    return ImportResult(
                        "unchanged",
                        offer_id,
                        str(current["id"]),
                        int(current["revision_number"]),
                        str(current["snapshot_id"]),
                        digest,
                        object_ref,
                        _identity_dict(identity),
                        _suggestions(connection, offer_id),
                    )
                latest = connection.execute(
                    "SELECT MAX(revision_number) FROM offer_revision WHERE offer_id = ?",
                    (offer_id,),
                ).fetchone()[0]
                outcome, number = "revision_created", int(latest) + 1

            snapshot = connection.execute(
                "SELECT id FROM source_snapshot WHERE content_sha256 = ?", (digest,)
            ).fetchone()
            if snapshot is None:
                snapshot_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO source_snapshot (id, source_ref, retrieved_at, mime, "
                    "content_sha256, size_bytes, connector_version, object_ref) "
                    "VALUES (?, ?, ?, 'text/plain', ?, ?, ?, ?)",
                    (snapshot_id, label, now, digest, len(raw), CONNECTOR_VERSION, object_ref),
                )
            else:
                snapshot_id = str(snapshot["id"])

            revision_id = str(uuid.uuid4())
            provenance = {
                "schema_version": PROVENANCE_SCHEMA_VERSION,
                "snapshot_id": snapshot_id,
                "encoding": "utf-8",
                "offset_unit": "unicode_code_point",
                "fields": normalized.provenance,
            }
            connection.execute(
                "INSERT INTO offer_revision (id, offer_id, revision_number, snapshot_id, title, "
                "company, locations_json, contract, salary_raw_text, description, apply_url, "
                "provenance_json, normalized_sha256, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    revision_id,
                    offer_id,
                    number,
                    snapshot_id,
                    normalized.title,
                    normalized.company,
                    None
                    if normalized.locations is None
                    else json.dumps(list(normalized.locations), ensure_ascii=False),
                    normalized.contract,
                    normalized.salary_raw_text,
                    normalized.description,
                    normalized.apply_url,
                    json.dumps(provenance, sort_keys=True, ensure_ascii=False),
                    normalized.normalized_sha256(),
                    now,
                ),
            )
            _record_acquisition(
                connection,
                snapshot_id=snapshot_id,
                revision_id=revision_id,
                source_ref=label,
                source_id=identity.external_id,
                provider=identity.provider,
                board=identity.board,
                retrieved_at=now,
            )
            canonical = canonicalize_url(normalized.apply_url) if normalized.apply_url else None
            connection.execute(
                "UPDATE offer SET current_revision_id = ?, "
                "canonical_url = COALESCE(?, canonical_url) WHERE id = ?",
                (revision_id, canonical, offer_id),
            )
            _refresh_suggestions(connection, offer_id, normalized.title, normalized.company, now)
            suggestions = _suggestions(connection, offer_id)
    return ImportResult(
        outcome,
        offer_id,
        revision_id,
        number,
        snapshot_id,
        digest,
        object_ref,
        _identity_dict(identity),
        suggestions,
    )


def _record_acquisition(
    connection: sqlite3.Connection,
    *,
    snapshot_id: str,
    revision_id: str,
    source_ref: str,
    source_id: str,
    provider: str,
    board: str,
    retrieved_at: str,
) -> None:
    connection.execute(
        "INSERT INTO source_acquisition (id, snapshot_id, offer_revision_id, source_ref, "
        "source_id, provider, board, retrieved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid.uuid4()),
            snapshot_id,
            revision_id,
            source_ref,
            source_id,
            provider,
            board,
            retrieved_at,
        ),
    )


def _identity_values(identity: OfferIdentity) -> tuple[str, str, str, str]:
    return identity.provider, identity.board, identity.external_id, identity.kind


def _identity_dict(identity: OfferIdentity) -> dict[str, str]:
    return {
        "provider": identity.provider,
        "board": identity.board,
        "external_id": identity.external_id,
        "kind": identity.kind,
    }


def _refresh_suggestions(
    connection: sqlite3.Connection, offer_id: str, title: str | None, company: str | None, now: str
) -> None:
    """Record fuzzy cross-offer hints. Offers are never merged or altered by this."""
    others = connection.execute(
        "SELECT o.id, r.title, r.company FROM offer o "
        "JOIN offer_revision r ON r.id = o.current_revision_id WHERE o.id != ?",
        (offer_id,),
    ).fetchall()
    for other in others:
        hint = suggest_duplicate(title, company, other["title"], other["company"])
        if hint is None:
            continue
        first, second = sorted((offer_id, str(other["id"])))
        connection.execute(
            "INSERT OR IGNORE INTO duplicate_suggestion (id, offer_a_id, offer_b_id, score, "
            "reason, status, created_at) VALUES (?, ?, ?, ?, ?, 'SUGGESTED', ?)",
            (str(uuid.uuid4()), first, second, hint.score, hint.reason, now),
        )


def _suggestions(connection: sqlite3.Connection, offer_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT d.id, d.score, d.reason, d.status, d.created_at, other.id AS other_offer_id, "
        "r.title AS other_title, r.company AS other_company "
        "FROM duplicate_suggestion d "
        "JOIN offer other ON other.id = CASE WHEN d.offer_a_id = ? THEN d.offer_b_id "
        "ELSE d.offer_a_id END "
        "JOIN offer_revision r ON r.id = other.current_revision_id "
        "WHERE d.offer_a_id = ? OR d.offer_b_id = ? ORDER BY d.created_at, d.rowid",
        (offer_id, offer_id, offer_id),
    ).fetchall()
    return [dict(row) for row in rows]


def list_offers(data_dir: Path) -> list[dict[str, Any]]:
    with closing(connect(database_path_for(data_dir))) as connection:
        rows = connection.execute(
            "SELECT o.id, o.provider, o.board, o.external_id, o.identity_kind, o.created_at, "
            "r.id AS current_revision_id, r.revision_number, r.title, r.company, "
            "r.locations_json, r.contract, a.id AS application_id, "
            "(SELECT COUNT(*) FROM duplicate_suggestion d "
            " WHERE d.offer_a_id = o.id OR d.offer_b_id = o.id) AS suggestion_count "
            "FROM offer o JOIN offer_revision r ON r.id = o.current_revision_id "
            "LEFT JOIN application a ON a.offer_id = o.id ORDER BY o.created_at DESC, o.rowid DESC"
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["locations"] = _loads(item.pop("locations_json"))
        result.append(item)
    return result


def _loads(value: str | None) -> Any:
    return None if value is None else json.loads(value)


def get_offer(data_dir: Path, offer_id: str) -> dict[str, Any]:
    with closing(connect(database_path_for(data_dir))) as connection:
        offer = connection.execute("SELECT * FROM offer WHERE id = ?", (offer_id,)).fetchone()
        if offer is None:
            raise NotFound("Offer not found.")
        revisions = connection.execute(
            "SELECT r.*, s.source_ref, s.retrieved_at, s.mime, s.content_sha256, s.size_bytes, "
            "s.object_ref, s.connector_version FROM offer_revision r "
            "JOIN source_snapshot s ON s.id = r.snapshot_id WHERE r.offer_id = ? "
            "ORDER BY r.revision_number",
            (offer_id,),
        ).fetchall()
        application = connection.execute(
            "SELECT id, stage FROM application WHERE offer_id = ?", (offer_id,)
        ).fetchone()
        suggestions = _suggestions(connection, offer_id)
        acquisitions_by_revision = {
            str(row["id"]): [
                dict(acquisition)
                for acquisition in connection.execute(
                    "SELECT id, snapshot_id, source_ref, source_id, provider, board, retrieved_at "
                    "FROM source_acquisition WHERE offer_revision_id = ? ORDER BY retrieved_at, id",
                    (row["id"],),
                ).fetchall()
            ]
            for row in revisions
        }
    revision_items = []
    for row in revisions:
        revision_items.append(
            {
                "id": row["id"],
                "revision_number": row["revision_number"],
                "created_at": row["created_at"],
                "normalized_sha256": row["normalized_sha256"],
                "fields": {
                    "title": row["title"],
                    "company": row["company"],
                    "locations": _loads(row["locations_json"]),
                    "contract": row["contract"],
                    "salary_raw_text": row["salary_raw_text"],
                    "description": row["description"],
                    "apply_url": row["apply_url"],
                },
                "provenance": json.loads(row["provenance_json"]),
                "acquisitions": acquisitions_by_revision[str(row["id"])],
                "snapshot": {
                    "id": row["snapshot_id"],
                    # Legacy attributes: first stored source only. `acquisitions` is authoritative.
                    "provenance_scope": "first_stored_source",
                    "source_ref": row["source_ref"],
                    "retrieved_at": row["retrieved_at"],
                    "mime": row["mime"],
                    "content_sha256": row["content_sha256"],
                    "size_bytes": row["size_bytes"],
                    "object_ref": row["object_ref"],
                    "connector_version": row["connector_version"],
                },
            }
        )
    return {
        "id": offer["id"],
        "provider": offer["provider"],
        "board": offer["board"],
        "external_id": offer["external_id"],
        "identity_kind": offer["identity_kind"],
        "canonical_url": offer["canonical_url"],
        "created_at": offer["created_at"],
        "current_revision_id": offer["current_revision_id"],
        "revisions": revision_items,
        "duplicate_suggestions": suggestions,
        "application": None if application is None else dict(application),
    }


def read_snapshot(data_dir: Path, snapshot_id: str) -> bytes:
    """Return the immutable source bytes after verifying them against the stored hash."""
    with closing(connect(database_path_for(data_dir))) as connection:
        row = connection.execute(
            "SELECT object_ref, content_sha256 FROM source_snapshot WHERE id = ?", (snapshot_id,)
        ).fetchone()
    if row is None:
        raise NotFound("Snapshot not found.")
    return ObjectStore(data_dir).read_verified(str(row["object_ref"]), str(row["content_sha256"]))
