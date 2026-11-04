"""Durable SQLite job queue: leases, generation fencing and bounded restart recovery.

State lives only in SQL. A worker may finish a job only with the generation it was handed, so a
worker whose lease expired (and whose job was reclaimed) can never overwrite the newer attempt.
Never use this queue to retry an external submission: those have their own safety state machine.
"""

import hashlib
import json
import uuid
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from career_engine.clock import iso, utc_now
from career_engine.db import connect, write_transaction

Clock = Callable[[], datetime]


@dataclass(frozen=True)
class ClaimedJob:
    id: str
    kind: str
    payload: dict[str, Any]
    generation: int
    attempts: int
    lease_expires_at: str


class JobQueue:
    def __init__(self, db_path: Path | None = None, clock: Clock = utc_now) -> None:
        self._db_path = db_path
        self._clock = clock

    def enqueue(self, kind: str, payload: dict[str, Any], max_attempts: int = 3) -> str:
        """Idempotent per (kind, payload): the same logical job is never queued twice."""
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        input_hash = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        now = iso(self._clock())
        with closing(connect(self._db_path)) as connection:
            with write_transaction(connection):
                existing = connection.execute(
                    "SELECT id FROM job WHERE kind = ? AND input_hash = ?", (kind, input_hash)
                ).fetchone()
                if existing is not None:
                    return str(existing["id"])
                job_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO job (id, kind, input_hash, payload_json, status, max_attempts, "
                    "created_at, updated_at) VALUES (?, ?, ?, ?, 'QUEUED', ?, ?, ?)",
                    (job_id, kind, input_hash, encoded, max_attempts, now, now),
                )
                return job_id

    def reconcile_expired(self) -> int:
        """Restart handling: expired RUNNING leases go back to QUEUED, or FAILED when exhausted."""
        with closing(connect(self._db_path)) as connection:
            with write_transaction(connection):
                return self._reconcile(connection)

    def _reconcile(self, connection: Any) -> int:
        now = iso(self._clock())
        cursor = connection.execute(
            "UPDATE job SET status = CASE WHEN attempts < max_attempts THEN 'QUEUED' "
            "ELSE 'FAILED' END, lease_expires_at = NULL, updated_at = ?, "
            "error_code = CASE WHEN attempts < max_attempts THEN 'LEASE_EXPIRED' "
            "ELSE 'LEASE_EXPIRED_MAX_ATTEMPTS' END "
            "WHERE status = 'RUNNING' AND lease_expires_at < ?",
            (now, now),
        )
        return int(cursor.rowcount)

    def claim(self, lease_seconds: int = 60) -> ClaimedJob | None:
        now = self._clock()
        with closing(connect(self._db_path)) as connection:
            with write_transaction(connection):
                self._reconcile(connection)
                row = connection.execute(
                    "SELECT id FROM job WHERE status = 'QUEUED' ORDER BY created_at, rowid LIMIT 1"
                ).fetchone()
                if row is None:
                    return None
                lease = iso(now + timedelta(seconds=lease_seconds))
                connection.execute(
                    "UPDATE job SET status = 'RUNNING', generation = generation + 1, "
                    "attempts = attempts + 1, lease_expires_at = ?, error_code = NULL, "
                    "updated_at = ? WHERE id = ?",
                    (lease, iso(now), row["id"]),
                )
                claimed = connection.execute(
                    "SELECT * FROM job WHERE id = ?", (row["id"],)
                ).fetchone()
        return ClaimedJob(
            id=str(claimed["id"]),
            kind=str(claimed["kind"]),
            payload=json.loads(claimed["payload_json"]),
            generation=int(claimed["generation"]),
            attempts=int(claimed["attempts"]),
            lease_expires_at=str(claimed["lease_expires_at"]),
        )

    def _finish(
        self,
        job_id: str,
        generation: int,
        status_sql: str,
        result: dict[str, Any] | None,
        error_code: str | None,
    ) -> bool:
        with closing(connect(self._db_path)) as connection:
            with write_transaction(connection):
                cursor = connection.execute(
                    f"UPDATE job SET status = {status_sql}, lease_expires_at = NULL, "
                    "result_json = ?, error_code = ?, updated_at = ? "
                    "WHERE id = ? AND status = 'RUNNING' AND generation = ?",
                    (
                        None if result is None else json.dumps(result, sort_keys=True),
                        error_code,
                        iso(self._clock()),
                        job_id,
                        generation,
                    ),
                )
                return cursor.rowcount == 1

    def complete(self, job_id: str, generation: int, result: dict[str, Any]) -> bool:
        return self._finish(job_id, generation, "'SUCCEEDED'", result, None)

    def fail(self, job_id: str, generation: int, error_code: str, retryable: bool = True) -> bool:
        status = (
            "CASE WHEN attempts < max_attempts THEN 'QUEUED' ELSE 'FAILED' END"
            if retryable
            else "'FAILED'"
        )
        return self._finish(job_id, generation, status, None, error_code)

    def block(self, job_id: str, generation: int, error_code: str) -> bool:
        return self._finish(job_id, generation, "'BLOCKED'", None, error_code)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with closing(connect(self._db_path)) as connection:
            row = connection.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
        return None if row is None else dict(row)
