"""T04/T15/REQ-005/REQ-017: separate application records, manifest hashes, atomic transitions."""

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest
from helpers import fixture_bytes

from career_engine.application.applications import (
    create_application,
    get_application,
    list_applications,
    transition_application,
)
from career_engine.application.integrity import verify_integrity
from career_engine.application.offers import get_offer, import_posting
from career_engine.config import database_path_for
from career_engine.db import connect, initialize
from career_engine.domain.errors import Conflict, InvalidTransition, NotFound, ValidationFailed
from career_engine.infrastructure.objects import sha256_hex


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    initialize(database_path_for(tmp_path))
    return tmp_path


@pytest.fixture
def offer_id(data_dir: Path) -> str:
    return import_posting(data_dir, fixture_bytes("sample-business-manager.txt")).offer_id


def rows(data_dir: Path, sql: str) -> list[sqlite3.Row]:
    with closing(connect(database_path_for(data_dir))) as connection:
        return connection.execute(sql).fetchall()


def test_application_is_a_separate_record_with_a_hashed_manifest(
    data_dir: Path, offer_id: str
) -> None:
    application = create_application(data_dir, offer_id)
    assert application["id"] != offer_id and application["offer_id"] == offer_id
    assert application["stage"] == "DRAFT" and application["version"] == 1
    assert application["recruiter_status"] is None  # unknown, not guessed
    manifest_file = data_dir / application["dossier_path"] / "manifest.json"
    assert sha256_hex(manifest_file.read_bytes()) == application["manifest_sha256"]
    manifest = json.loads(manifest_file.read_text())
    assert manifest["offer_id"] == offer_id and manifest["application_id"] == application["id"]
    offer = get_offer(data_dir, offer_id)
    assert manifest["source_content_sha256"] == offer["revisions"][0]["snapshot"]["content_sha256"]
    assert offer["application"]["id"] == application["id"]
    assert [e["kind"] for e in application["events"]] == ["CREATED"]
    assert verify_integrity(data_dir)["ok"] is True


def test_importing_never_creates_an_application(data_dir: Path, offer_id: str) -> None:
    assert list_applications(data_dir) == []
    assert not (data_dir / "applications").exists()


def test_second_application_for_the_same_offer_is_a_conflict_without_residue(
    data_dir: Path, offer_id: str
) -> None:
    create_application(data_dir, offer_id)
    with pytest.raises(Conflict) as error:
        create_application(data_dir, offer_id)
    assert error.value.code == "APPLICATION_EXISTS"
    assert len(rows(data_dir, "SELECT id FROM application")) == 1
    assert len(list((data_dir / "applications").iterdir())) == 1


def test_unknown_offer_is_not_found(data_dir: Path) -> None:
    with pytest.raises(NotFound):
        create_application(data_dir, "missing")


def test_failed_creation_removes_the_new_dossier_folder(data_dir: Path, offer_id: str) -> None:
    with closing(connect(database_path_for(data_dir))) as connection:
        connection.execute(
            "CREATE TRIGGER inject BEFORE INSERT ON application_event "
            "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        create_application(data_dir, offer_id)
    assert rows(data_dir, "SELECT id FROM application") == []
    assert list((data_dir / "applications").iterdir()) == []


def test_transition_updates_stage_and_appends_event_atomically(
    data_dir: Path, offer_id: str
) -> None:
    created = create_application(data_dir, offer_id)
    updated = transition_application(
        data_dir, created["id"], "PREPARING", "Starting preparation", 1, actor="tester"
    )
    assert (updated["stage"], updated["version"]) == ("PREPARING", 2)
    event = updated["events"][-1]
    assert (event["from_stage"], event["to_stage"], event["actor"]) == (
        "DRAFT",
        "PREPARING",
        "tester",
    )
    assert event["reason"] == "Starting preparation" and event["resulting_version"] == 2
    assert event["created_at"].endswith("+00:00")


@pytest.mark.parametrize("trigger_table", ["application", "application_event"])
def test_injected_sql_error_leaves_no_partial_transition_or_orphan_event(
    data_dir: Path, offer_id: str, trigger_table: str
) -> None:
    """T15: whichever statement fails, neither the stage change nor its history event persists."""
    created = create_application(data_dir, offer_id)
    event_ddl = (
        "CREATE TRIGGER inject BEFORE INSERT ON application_event WHEN NEW.kind = 'STAGE_CHANGED' "
        "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
    )
    app_ddl = (
        "CREATE TRIGGER inject BEFORE UPDATE ON application "
        "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
    )
    with closing(connect(database_path_for(data_dir))) as connection:
        connection.execute(app_ddl if trigger_table == "application" else event_ddl)
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        transition_application(data_dir, created["id"], "PREPARING", "x", 1)
    after = get_application(data_dir, created["id"])
    assert (after["stage"], after["version"]) == ("DRAFT", 1)
    assert [e["kind"] for e in after["events"]] == ["CREATED"]


def test_stale_version_conflicts_and_changes_nothing(data_dir: Path, offer_id: str) -> None:
    created = create_application(data_dir, offer_id)
    transition_application(data_dir, created["id"], "PREPARING", "first", 1)
    with pytest.raises(Conflict) as error:
        transition_application(data_dir, created["id"], "BLOCKED", "second", 1)
    assert error.value.code == "VERSION_CONFLICT"
    current = get_application(data_dir, created["id"])
    assert (current["stage"], len(current["events"])) == ("PREPARING", 2)


@pytest.mark.parametrize(
    "target", ["APPROVED", "SUBMITTING", "SUBMITTED", "SUBMISSION_UNKNOWN", "NOPE"]
)
def test_stages_that_need_later_milestone_gates_cannot_be_set(
    data_dir: Path, offer_id: str, target: str
) -> None:
    created = create_application(data_dir, offer_id)
    with pytest.raises(InvalidTransition):
        transition_application(data_dir, created["id"], target, "trying", 1)
    assert get_application(data_dir, created["id"])["stage"] == "DRAFT"


def test_same_stage_and_missing_reason_are_rejected(data_dir: Path, offer_id: str) -> None:
    created = create_application(data_dir, offer_id)
    with pytest.raises(InvalidTransition):
        transition_application(data_dir, created["id"], "DRAFT", "noop", 1)
    for reason in ("", "   ", "x" * 501):
        with pytest.raises(ValidationFailed):
            transition_application(data_dir, created["id"], "PREPARING", reason, 1)
    with pytest.raises(NotFound):
        transition_application(data_dir, "missing", "PREPARING", "r", 1)
    assert len(get_application(data_dir, created["id"])["events"]) == 1


def test_history_events_cannot_be_rewritten(data_dir: Path, offer_id: str) -> None:
    create_application(data_dir, offer_id)
    with closing(connect(database_path_for(data_dir))) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM application_event")


def test_tracker_row_is_bound_to_the_revision_seen_at_creation(
    data_dir: Path, offer_id: str
) -> None:
    created = create_application(data_dir, offer_id)
    import_posting(data_dir, fixture_bytes("sample-business-manager-r2.txt"))
    row = list_applications(data_dir)[0]
    assert row["id"] == created["id"]
    assert (row["offer_revision_number"], row["current_offer_revision_number"]) == (1, 2)


def test_tampered_or_missing_manifest_is_detected(data_dir: Path, offer_id: str) -> None:
    created = create_application(data_dir, offer_id)
    manifest = data_dir / created["dossier_path"] / "manifest.json"
    manifest.write_text("{}")
    report = verify_integrity(data_dir)
    assert report["ok"] is False and report["corrupt"] == [
        f"{created['dossier_path']}/manifest.json"
    ]
    manifest.unlink()
    assert verify_integrity(data_dir)["missing"] == [f"{created['dossier_path']}/manifest.json"]


def test_concurrent_creation_yields_one_application_and_one_dossier(
    data_dir: Path, offer_id: str
) -> None:
    outcomes: list[str] = []

    def run() -> None:
        try:
            create_application(data_dir, offer_id)
            outcomes.append("created")
        except Conflict:
            outcomes.append("conflict")

    threads = [threading.Thread(target=run) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(outcomes) == ["conflict"] * 5 + ["created"]
    assert len(rows(data_dir, "SELECT id FROM application")) == 1
    assert len(list((data_dir / "applications").iterdir())) == 1
    assert verify_integrity(data_dir)["orphan_dossiers"] == []
