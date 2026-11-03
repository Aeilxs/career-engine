"""T01/T03/T04/T21 integration: real SQLite and real object files under tmp_path."""

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import pytest
from helpers import fixture_bytes, posting

from career_engine.application.integrity import verify_integrity
from career_engine.application.offers import get_offer, import_posting, list_offers, read_snapshot
from career_engine.config import database_path_for
from career_engine.db import connect, initialize
from career_engine.domain.errors import IntegrityFailure, NotFound, ValidationFailed
from career_engine.infrastructure.objects import sha256_hex


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    initialize(database_path_for(tmp_path))
    return tmp_path


def count(data_dir: Path, table: str) -> int:
    with closing(connect(database_path_for(data_dir))) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def object_files(data_dir: Path) -> list[Path]:
    return sorted(path for path in (data_dir / "objects").rglob("*") if path.is_file())


def test_import_keeps_raw_bytes_normalizes_and_creates_no_application(data_dir: Path) -> None:
    raw = fixture_bytes("sample-business-manager.txt")
    result = import_posting(data_dir, raw, source_ref="sample-business-manager.txt")
    assert result.outcome == "created" and result.revision_number == 1
    assert result.content_sha256 == sha256_hex(raw)
    stored = data_dir / result.object_ref
    assert stored.read_bytes() == raw
    assert read_snapshot(data_dir, result.snapshot_id) == raw

    detail = get_offer(data_dir, result.offer_id)
    revision = detail["revisions"][0]
    assert revision["fields"]["title"] == "Business Manager — Industrial Energy"
    assert revision["fields"]["locations"] == ["Marseille, France"]
    assert revision["snapshot"]["source_ref"] == "sample-business-manager.txt"
    assert revision["snapshot"]["content_sha256"] == sha256_hex(raw)
    assert revision["provenance"]["snapshot_id"] == result.snapshot_id
    assert revision["provenance"]["fields"]["title"]["status"] == "extracted"
    assert detail["identity_kind"] == "native"
    assert detail["external_id"] == "synthetic/board/offer-001"
    assert detail["application"] is None
    assert (count(data_dir, "offer"), count(data_dir, "application")) == (1, 0)


def test_ten_identical_imports_yield_one_offer_one_revision(data_dir: Path) -> None:
    raw = fixture_bytes("sample-business-manager.txt")
    outcomes = [import_posting(data_dir, raw).outcome for _ in range(10)]
    assert outcomes == ["created"] + ["unchanged"] * 9
    assert [
        count(data_dir, t)
        for t in ("offer", "offer_revision", "source_snapshot", "source_acquisition")
    ] == [1, 1, 1, 10]
    assert len(object_files(data_dir)) == 1


def test_identical_content_keeps_distinct_source_acquisitions(data_dir: Path) -> None:
    raw = fixture_bytes("sample-business-manager.txt")
    assert [
        count(data_dir, table)
        for table in ("offer", "offer_revision", "source_snapshot", "source_acquisition")
    ] == [0, 0, 0, 0]
    assert object_files(data_dir) == []
    first = import_posting(
        data_dir,
        raw,
        source_ref="provider-a-capture",
        source_id="provider-a-123",
        provider="provider-a",
        board="board-a",
    )
    second = import_posting(
        data_dir,
        raw,
        source_ref="provider-b-capture",
        source_id="provider-b-456",
        provider="provider-b",
        board="board-b",
    )

    assert first.content_sha256 == second.content_sha256
    assert first.snapshot_id == second.snapshot_id
    assert first.offer_id != second.offer_id
    assert (count(data_dir, "offer"), count(data_dir, "offer_revision")) == (2, 2)
    assert (count(data_dir, "source_snapshot"), count(data_dir, "source_acquisition")) == (1, 2)
    assert len(object_files(data_dir)) == 1
    first_acquisition = get_offer(data_dir, first.offer_id)["revisions"][0]["acquisitions"]
    second_acquisition = get_offer(data_dir, second.offer_id)["revisions"][0]["acquisitions"]
    assert len(first_acquisition) == len(second_acquisition) == 1
    assert {
        "source_ref": first_acquisition[0]["source_ref"],
        "source_id": first_acquisition[0]["source_id"],
        "provider": first_acquisition[0]["provider"],
        "board": first_acquisition[0]["board"],
    } == {
        "source_ref": "provider-a-capture",
        "source_id": "provider-a-123",
        "provider": "provider-a",
        "board": "board-a",
    }
    assert {
        "source_ref": second_acquisition[0]["source_ref"],
        "source_id": second_acquisition[0]["source_id"],
        "provider": second_acquisition[0]["provider"],
        "board": second_acquisition[0]["board"],
    } == {
        "source_ref": "provider-b-capture",
        "source_id": "provider-b-456",
        "provider": "provider-b",
        "board": "board-b",
    }
    assert first_acquisition[0]["retrieved_at"] and second_acquisition[0]["retrieved_at"]
    first_snapshot = get_offer(data_dir, first.offer_id)["revisions"][0]["snapshot"]
    second_snapshot = get_offer(data_dir, second.offer_id)["revisions"][0]["snapshot"]
    assert first_snapshot == second_snapshot
    assert first_snapshot["provenance_scope"] == "first_stored_source"
    assert first_snapshot["source_ref"] == "provider-a-capture"
    assert first_snapshot["retrieved_at"] == first_acquisition[0]["retrieved_at"]
    assert second_acquisition[0]["source_ref"] == "provider-b-capture"
    assert second_acquisition[0]["source_ref"] != second_snapshot["source_ref"]


def test_changed_source_creates_r2_and_leaves_r1_intact(data_dir: Path) -> None:
    first = import_posting(data_dir, fixture_bytes("sample-business-manager.txt"))
    before = get_offer(data_dir, first.offer_id)["revisions"][0]
    second = import_posting(data_dir, fixture_bytes("sample-business-manager-r2.txt"))
    assert second.outcome == "revision_created" and second.revision_number == 2
    assert second.offer_id == first.offer_id and second.snapshot_id != first.snapshot_id
    detail = get_offer(data_dir, first.offer_id)
    assert [r["revision_number"] for r in detail["revisions"]] == [1, 2]
    assert detail["revisions"][0] == before
    assert detail["revisions"][1]["fields"]["locations"] == [
        "Marseille and Aix-en-Provence, France"
    ]
    assert detail["current_revision_id"] == second.revision_id
    assert (count(data_dir, "offer"), count(data_dir, "source_snapshot")) == (1, 2)
    assert len(object_files(data_dir)) == 2


def test_reverting_to_earlier_content_is_a_new_revision_sharing_the_snapshot(
    data_dir: Path,
) -> None:
    r1 = import_posting(data_dir, fixture_bytes("sample-business-manager.txt"))
    import_posting(data_dir, fixture_bytes("sample-business-manager-r2.txt"))
    r3 = import_posting(data_dir, fixture_bytes("sample-business-manager.txt"))
    assert r3.outcome == "revision_created" and r3.revision_number == 3
    assert r3.snapshot_id == r1.snapshot_id
    assert (count(data_dir, "offer_revision"), count(data_dir, "source_snapshot")) == (3, 2)


def test_similar_title_from_distinct_source_is_separate_offer_with_suggestion(
    data_dir: Path,
) -> None:
    first = import_posting(data_dir, fixture_bytes("sample-business-manager.txt"))
    second = import_posting(data_dir, fixture_bytes("sample-similar-distinct.txt"))
    assert second.outcome == "created" and second.offer_id != first.offer_id
    assert count(data_dir, "offer") == 2
    assert len(second.duplicate_suggestions) == 1
    suggestion = second.duplicate_suggestions[0]
    assert suggestion["other_offer_id"] == first.offer_id and suggestion["score"] == 1.0
    assert suggestion["status"] == "SUGGESTED"
    assert len(get_offer(data_dir, first.offer_id)["duplicate_suggestions"]) == 1
    # Re-importing neither duplicates the suggestion nor merges anything.
    import_posting(data_dir, fixture_bytes("sample-similar-distinct.txt"))
    import_posting(data_dir, fixture_bytes("sample-business-manager.txt"))
    assert (count(data_dir, "offer"), count(data_dir, "duplicate_suggestion")) == (2, 1)
    assert {o["suggestion_count"] for o in list_offers(data_dir)} == {1}


def test_unrelated_offers_get_no_suggestion(data_dir: Path) -> None:
    import_posting(data_dir, posting(title="Chief Financial Officer", source_id="a/1"))
    other = import_posting(data_dir, posting(title="Warehouse Operator", source_id="a/2"))
    assert other.duplicate_suggestions == []


def test_url_identity_ignores_tracking_but_not_identifying_parameters(data_dir: Path) -> None:
    def text(url: str) -> bytes:
        return f"Title: Analyst\nCompany: Acme\nApplication URL: {url}\n".encode()

    a = import_posting(data_dir, text("https://example.org/job?gh_jid=1&utm_source=newsletter"))
    b = import_posting(data_dir, text("https://EXAMPLE.org/job?gh_jid=1#apply"))
    c = import_posting(data_dir, text("https://example.org/job?gh_jid=2"))
    assert a.offer_id == b.offer_id and b.outcome == "revision_created"  # raw bytes differ: R2
    assert c.offer_id != a.offer_id
    assert a.identity["kind"] == "url"


def test_identity_override_and_provider_scoping(data_dir: Path) -> None:
    raw = posting(source_id="12345")
    a = import_posting(data_dir, raw, provider="boardA")
    b = import_posting(data_dir, raw, provider="boardB")
    assert a.offer_id != b.offer_id  # same native ID on different providers: never merged
    c = import_posting(data_dir, raw, source_id="custom-id")
    assert c.identity["external_id"] == "custom-id" and c.offer_id not in {a.offer_id, b.offer_id}


@pytest.mark.parametrize("raw", [b"", b"\x00\x01binary", b"Title: \xff", b"x" * (1024 * 1024 + 1)])
def test_rejected_input_leaves_no_rows_and_no_files(data_dir: Path, raw: bytes) -> None:
    with pytest.raises(ValidationFailed):
        import_posting(data_dir, raw)
    assert [count(data_dir, t) for t in ("offer", "offer_revision", "source_snapshot")] == [0, 0, 0]
    assert object_files(data_dir) == []


def test_invalid_metadata_is_rejected_before_any_write(data_dir: Path) -> None:
    with pytest.raises(ValidationFailed):
        import_posting(data_dir, posting(), source_ref="bad\nlabel")
    assert object_files(data_dir) == [] and count(data_dir, "offer") == 0


def test_sql_failure_after_object_write_leaves_no_half_written_rows(data_dir: Path) -> None:
    with closing(connect(database_path_for(data_dir))) as connection:
        connection.execute(
            "CREATE TRIGGER inject_failure BEFORE INSERT ON offer_revision "
            "BEGIN SELECT RAISE(ABORT, 'injected failure'); END"
        )
    raw = posting()
    with pytest.raises(sqlite3.IntegrityError, match="injected failure"):
        import_posting(data_dir, raw)
    assert [count(data_dir, t) for t in ("offer", "offer_revision", "source_snapshot")] == [0, 0, 0]
    report = verify_integrity(data_dir)
    assert report["ok"] is True
    assert report["orphan_objects"] == [f"objects/sha256/{sha256_hex(raw)[:2]}/{sha256_hex(raw)}"]

    with closing(connect(database_path_for(data_dir))) as connection:
        connection.execute("DROP TRIGGER inject_failure")
    assert import_posting(data_dir, raw).outcome == "created"
    assert verify_integrity(data_dir)["orphan_objects"] == []


def test_missing_and_corrupt_objects_are_detected_then_repaired_by_reimport(
    data_dir: Path,
) -> None:
    raw = fixture_bytes("sample-business-manager.txt")
    result = import_posting(data_dir, raw)
    assert verify_integrity(data_dir)["ok"] is True
    target = data_dir / result.object_ref

    target.write_bytes(raw + b"tamper")
    report = verify_integrity(data_dir)
    assert report["ok"] is False and report["corrupt"] == [result.object_ref]
    with pytest.raises(IntegrityFailure) as corrupt:
        read_snapshot(data_dir, result.snapshot_id)
    assert corrupt.value.code == "OBJECT_CORRUPT"

    target.unlink()
    report = verify_integrity(data_dir)
    assert report["ok"] is False and report["missing"] == [result.object_ref]
    with pytest.raises(IntegrityFailure) as missing:
        read_snapshot(data_dir, result.snapshot_id)
    assert missing.value.code == "OBJECT_MISSING"

    assert import_posting(data_dir, raw).outcome == "unchanged"  # same bytes re-supplied
    repaired = verify_integrity(data_dir)
    assert repaired["ok"] is True and repaired["missing"] == [] and repaired["corrupt"] == []


def test_records_survive_a_new_connection_and_process_state(data_dir: Path) -> None:
    result = import_posting(data_dir, fixture_bytes("sample-business-manager.txt"))
    initialize(database_path_for(data_dir))  # what a restarted process does on boot
    detail = get_offer(data_dir, result.offer_id)
    assert detail["revisions"][0]["snapshot"]["object_ref"] == result.object_ref
    assert verify_integrity(data_dir)["ok"] is True
    with pytest.raises(NotFound):
        get_offer(data_dir, "does-not-exist")
    with pytest.raises(NotFound):
        read_snapshot(data_dir, "does-not-exist")


def test_formula_like_and_hostile_text_is_stored_verbatim(data_dir: Path) -> None:
    hostile = "=1+1"
    result = import_posting(
        data_dir,
        posting(title=hostile, description="<img src=x onerror=alert(1)> =cmd|' /C calc'!A0"),
    )
    fields = get_offer(data_dir, result.offer_id)["revisions"][0]["fields"]
    assert fields["title"] == hostile
    assert fields["description"] == "<img src=x onerror=alert(1)> =cmd|' /C calc'!A0"
    with closing(connect(database_path_for(data_dir))) as connection:
        row = connection.execute("SELECT title, provenance_json FROM offer_revision").fetchone()
    assert row["title"] == hostile and json.loads(row["provenance_json"])["schema_version"] == 1


def test_concurrent_identical_imports_create_a_single_offer(data_dir: Path) -> None:
    raw = fixture_bytes("sample-business-manager.txt")
    outcomes: list[str] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            outcomes.append(import_posting(data_dir, raw).outcome)
        except BaseException as error:
            errors.append(error)

    threads = [threading.Thread(target=run) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    assert sorted(outcomes) == ["created"] + ["unchanged"] * 7
    assert [count(data_dir, t) for t in ("offer", "offer_revision", "source_snapshot")] == [1, 1, 1]
