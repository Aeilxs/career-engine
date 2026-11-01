"""CLI uses the same use cases as HTTP; failure paths exit non-zero without partial data."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import FIXTURES
from xlsx_reader import read_xlsx

from career_engine.cli import main
from career_engine.web import app

SAMPLE = str(FIXTURES / "sample-business-manager.txt")


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_ingest_application_export_flow(
    isolated_data: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code, out, _ = run(capsys, "ingest", "--file", SAMPLE)
    imported = json.loads(out)
    assert code == 0 and imported["outcome"] == "created"
    code, out, _ = run(capsys, "ingest", "--file", SAMPLE)
    assert code == 0 and json.loads(out)["outcome"] == "unchanged"

    code, out, _ = run(capsys, "application", "create", "--offer", imported["offer_id"])
    application = json.loads(out)
    assert code == 0 and application["stage"] == "DRAFT"
    assert application["events"][0]["actor"] == "cli"
    code, _, err = run(capsys, "application", "create", "--offer", imported["offer_id"])
    assert code == 3 and json.loads(err)["error_code"] == "APPLICATION_EXISTS"

    base = ["application", "transition", application["id"], "--reason", "cli test"]
    code, out, _ = run(capsys, *base, "--to", "PREPARING", "--expected-version", "1")
    assert code == 0 and json.loads(out)["version"] == 2
    code, _, err = run(capsys, *base, "--to", "BLOCKED", "--expected-version", "1")
    assert code == 3 and json.loads(err)["error_code"] == "VERSION_CONFLICT"
    code, _, err = run(capsys, *base, "--to", "SUBMITTED", "--expected-version", "2")
    assert code == 4 and json.loads(err)["error_code"] == "INVALID_TRANSITION"

    output = tmp_path / "applications.xlsx"
    code, out, _ = run(capsys, "export", "--format", "xlsx", "--output", str(output))
    assert code == 0 and json.loads(out)["bytes"] == output.stat().st_size
    assert read_xlsx(output.read_bytes())["Applications"].rows[1][7] == "PREPARING"

    # Same use cases and same database as the HTTP API.
    with TestClient(app) as client:
        assert client.get(f"/api/applications/{application['id']}").json()["stage"] == "PREPARING"

    code, out, _ = run(capsys, "verify")
    assert code == 0 and json.loads(out)["ok"] is True
    code, out, _ = run(capsys, "offers", "list")
    assert code == 0 and len(json.loads(out)) == 1


def test_missing_file_exits_nonzero_and_writes_nothing(
    isolated_data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = run(capsys, "ingest", "--file", str(isolated_data / "absent.txt"))
    assert code == 2 and out == "" and json.loads(err)["error_code"] == "FILE_ERROR"
    code, out, _ = run(capsys, "offers", "list")
    assert json.loads(out) == []
    assert not (isolated_data / "objects").exists()


def test_invalid_file_content_exits_2_without_data(
    isolated_data: Path, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    binary = tmp_path / "binary.txt"
    binary.write_bytes(b"\x00\x01\x02")
    code, _, err = run(capsys, "ingest", "--file", str(binary))
    assert code == 2 and json.loads(err)["error_code"] == "NOT_TEXT"
    assert not (isolated_data / "objects").exists()


def test_unknown_entities_and_bad_arguments(
    isolated_data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(capsys, "application", "create", "--offer", "nope")[0] == 2
    assert run(capsys, "offers", "show", "nope")[0] == 2
    with pytest.raises(SystemExit) as error:
        main(["export", "--format", "csv", "--output", "x"])
    assert error.value.code == 2


def test_verify_reports_tampering_with_exit_1(
    isolated_data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out, _ = run(capsys, "ingest", "--file", SAMPLE)
    (isolated_data / json.loads(out)["object_ref"]).write_bytes(b"tampered")
    code, out, _ = run(capsys, "verify")
    assert code == 1 and json.loads(out)["ok"] is False


def test_worker_once_is_idle_without_jobs(
    isolated_data: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = run(capsys, "worker", "--once")
    assert code == 0 and json.loads(out)["outcome"] == "IDLE"
