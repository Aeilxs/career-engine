"""XLSX projection of the tracker. SQL stays the source of truth; the file is never read back."""

import json
from contextlib import closing
from datetime import datetime
from pathlib import Path

from career_engine.clock import iso, utc_now
from career_engine.config import database_path_for
from career_engine.db import SCHEMA_VERSION, connect
from career_engine.infrastructure.objects import atomic_write_bytes
from career_engine.infrastructure.xlsx import CellValue, Column, Sheet, build_workbook

EXPORT_SCHEMA_VERSION = 1
APPLICATION_COLUMNS = (
    Column("application_id", 38),
    Column("offer_id", 38),
    Column("company", 28),
    Column("position", 36),
    Column("location", 28),
    Column("URL", 40),
    Column("imported_at", 20),
    Column("technical_stage", 18),
    Column("recruiter_status", 18),
    Column("revision", 10),
    Column("approved_at", 20),
    Column("confirmed_submitted_at", 24),
    Column("last_error", 24),
    Column("next_action", 24),
    Column("dossier_path", 48),
)


def build_applications_workbook(data_dir: Path, exported_at: datetime | None = None) -> bytes:
    """Build the workbook from one coherent read snapshot of the database."""
    moment = exported_at if exported_at is not None else utc_now()
    with closing(connect(database_path_for(data_dir))) as connection:
        connection.execute("BEGIN")
        try:
            records = connection.execute(
                "SELECT a.id, a.offer_id, r.company, r.title, r.locations_json, r.apply_url, "
                "o.created_at AS imported_at, a.stage, a.recruiter_status, "
                "r.revision_number, a.dossier_path "
                "FROM application a JOIN offer o ON o.id = a.offer_id "
                "JOIN offer_revision r ON r.id = a.offer_revision_id "
                "ORDER BY a.created_at, a.rowid"
            ).fetchall()
        finally:
            connection.rollback()

    rows: list[tuple[CellValue, ...]] = []
    for record in records:
        locations = (
            None if record["locations_json"] is None else json.loads(record["locations_json"])
        )
        rows.append(
            (
                record["id"],
                record["offer_id"],
                record["company"],
                record["title"],
                None if not locations else "; ".join(locations),
                record["apply_url"],
                datetime.fromisoformat(record["imported_at"]),
                record["stage"],
                record["recruiter_status"],
                int(record["revision_number"]),
                None,
                None,
                None,
                None,
                record["dossier_path"],
            )
        )
    metadata_rows: tuple[tuple[CellValue, ...], ...] = (
        ("schema_version", str(EXPORT_SCHEMA_VERSION)),
        ("database_schema_version", str(SCHEMA_VERSION)),
        ("exported_at", iso(moment)),
        ("timezone", "UTC"),
        ("filters", "none"),
        ("row_count", str(len(rows))),
    )
    return build_workbook(
        (
            Sheet("Applications", APPLICATION_COLUMNS, tuple(rows), autofilter=True),
            Sheet("Metadata", (Column("key", 26), Column("value", 40)), metadata_rows),
        )
    )


def write_applications_export(
    data_dir: Path, output: Path, exported_at: datetime | None = None
) -> int:
    """Write to a temporary file in the target directory, then atomically replace the target."""
    payload = build_applications_workbook(data_dir, exported_at)
    atomic_write_bytes(output, payload)
    return len(payload)
