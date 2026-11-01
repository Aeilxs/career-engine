"""T16: competing claims, expired leases and stale workers cannot double-process a job."""

import threading
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from career_engine.application.worker import run_once
from career_engine.db import connect, initialize
from career_engine.infrastructure.jobs import ClaimedJob, JobQueue


class FakeClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "career.db"
    initialize(path)
    return path


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def test_enqueue_is_idempotent_per_logical_job(db: Path, clock: FakeClock) -> None:
    queue = JobQueue(db, clock)
    first = queue.enqueue("scan", {"board": "a"})
    assert queue.enqueue("scan", {"board": "a"}) == first
    assert queue.enqueue("scan", {"board": "b"}) != first


def test_competing_threads_claim_a_job_exactly_once(db: Path, clock: FakeClock) -> None:
    queue = JobQueue(db, clock)
    queue.enqueue("scan", {"n": 1})
    claims: list[ClaimedJob | None] = []

    def claim() -> None:
        claims.append(queue.claim(60))

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    won = [claim for claim in claims if claim is not None]
    assert len(won) == 1 and won[0].generation == 1 and won[0].attempts == 1


def test_expired_lease_is_reclaimed_and_the_old_worker_is_fenced_off(
    db: Path, clock: FakeClock
) -> None:
    queue = JobQueue(db, clock)
    job_id = queue.enqueue("scan", {})
    old = queue.claim(30)
    assert old is not None and queue.claim(30) is None  # still leased
    clock.advance(31)  # the first worker is now considered dead
    new = queue.claim(30)
    assert new is not None and new.id == job_id and new.generation == 2
    assert queue.complete(old.id, old.generation, {"by": "old"}) is False
    assert queue.get(job_id)["status"] == "RUNNING"
    assert queue.complete(new.id, new.generation, {"by": "new"}) is True
    row = queue.get(job_id)
    assert row["status"] == "SUCCEEDED" and row["result_json"] == '{"by": "new"}'
    assert queue.complete(new.id, new.generation, {"again": True}) is False


def test_restart_recovery_is_bounded_by_max_attempts(db: Path, clock: FakeClock) -> None:
    queue = JobQueue(db, clock)
    job_id = queue.enqueue("scan", {}, max_attempts=2)
    for expected_status in ("QUEUED", "FAILED"):
        assert queue.claim(10) is not None
        clock.advance(11)  # process killed without finishing
        assert queue.reconcile_expired() == 1
        row = queue.get(job_id)
        assert row["status"] == expected_status
    assert row["error_code"] == "LEASE_EXPIRED_MAX_ATTEMPTS"
    assert queue.claim(10) is None


def test_failure_requeues_until_attempts_are_exhausted(db: Path, clock: FakeClock) -> None:
    queue = JobQueue(db, clock)
    job_id = queue.enqueue("scan", {}, max_attempts=2)
    first = queue.claim(10)
    assert first is not None and queue.fail(first.id, first.generation, "TIMEOUT")
    assert queue.get(job_id)["status"] == "QUEUED"
    second = queue.claim(10)
    assert second is not None and queue.fail(second.id, second.generation, "TIMEOUT")
    assert queue.get(job_id)["status"] == "FAILED" and queue.claim(10) is None


def test_non_retryable_failure_and_block_are_terminal(db: Path, clock: FakeClock) -> None:
    queue = JobQueue(db, clock)
    a, b = queue.enqueue("k", {"i": 1}), queue.enqueue("k", {"i": 2})
    first, second = queue.claim(10), queue.claim(10)
    assert first is not None and second is not None
    assert queue.fail(first.id, first.generation, "BAD_INPUT", retryable=False)
    assert queue.block(second.id, second.generation, "NEEDS_HUMAN")
    assert {queue.get(a)["status"], queue.get(b)["status"]} == {"FAILED", "BLOCKED"}


def test_state_survives_a_new_queue_instance(db: Path, clock: FakeClock) -> None:
    job_id = JobQueue(db, clock).enqueue("scan", {"x": 1})
    reopened = JobQueue(db, clock)
    assert reopened.get(job_id)["status"] == "QUEUED"
    with closing(connect(db)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM job").fetchone()[0] == 1


def test_worker_step_handles_idle_success_failure_and_unknown_kind(
    db: Path, clock: FakeClock
) -> None:
    queue = JobQueue(db, clock)
    assert run_once(queue, {}) == "IDLE"
    ok = queue.enqueue("ok", {"v": 1})
    assert run_once(queue, {"ok": lambda payload: {"echo": payload["v"]}}) == "SUCCEEDED"
    assert queue.get(ok)["status"] == "SUCCEEDED"

    def boom(_: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")

    bad = queue.enqueue("bad", {}, max_attempts=1)
    assert run_once(queue, {"bad": boom}) == "FAILED_OR_REQUEUED"
    assert (queue.get(bad)["status"], queue.get(bad)["error_code"]) == ("FAILED", "RuntimeError")
    unknown = queue.enqueue("mystery", {})
    assert run_once(queue, {}) == "BLOCKED"
    assert queue.get(unknown)["error_code"] == "UNKNOWN_JOB_KIND"
