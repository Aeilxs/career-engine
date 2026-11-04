"""HTTP-level J1 flow against real SQLite/files (T01–T04, T14, T15, T21)."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from helpers import fixture_bytes, posting
from xlsx_reader import read_xlsx

from career_engine.web import app

CSRF = {"X-Requested-With": "career-engine"}
TEXT = {**CSRF, "Content-Type": "text/plain; charset=utf-8"}


@pytest.fixture
def client(isolated_data: Path) -> Iterator[TestClient]:
    with TestClient(app, headers=CSRF) as test_client:
        yield test_client


def do_import(client: TestClient, raw: bytes, **params: str) -> dict:
    response = client.post("/api/imports", content=raw, params=params, headers=TEXT)
    assert response.status_code in (200, 201), response.text
    return {**response.json(), "_status": response.status_code}


def test_full_manual_flow_over_http(client: TestClient) -> None:
    raw = fixture_bytes("sample-business-manager.txt")
    created = do_import(client, raw, source_ref="sample-business-manager.txt")
    assert (created["_status"], created["outcome"]) == (201, "created")
    again = do_import(client, raw)
    assert (again["_status"], again["outcome"], again["offer_id"]) == (
        200,
        "unchanged",
        created["offer_id"],
    )

    listing = client.get("/api/offers").json()
    assert len(listing) == 1 and listing[0]["title"].startswith("Business Manager")
    assert listing[0]["application_id"] is None

    detail = client.get(f"/api/offers/{created['offer_id']}").json()
    snapshot_id = detail["revisions"][0]["snapshot"]["id"]
    source = client.get(f"/api/snapshots/{snapshot_id}/content")
    assert source.content == raw and source.headers["content-type"].startswith("text/plain")

    application = client.post("/api/applications", json={"offer_id": created["offer_id"]})
    assert application.status_code == 201 and application.json()["stage"] == "DRAFT"
    duplicate = client.post("/api/applications", json={"offer_id": created["offer_id"]})
    assert (duplicate.status_code, duplicate.json()["error_code"]) == (409, "APPLICATION_EXISTS")

    app_id = application.json()["id"]
    moved = client.post(
        f"/api/applications/{app_id}/transitions",
        json={"to_stage": "PREPARING", "reason": "Starting", "expected_version": 1},
    )
    assert moved.status_code == 200 and moved.json()["version"] == 2
    stale = client.post(
        f"/api/applications/{app_id}/transitions",
        json={"to_stage": "BLOCKED", "reason": "late", "expected_version": 1},
    )
    assert (stale.status_code, stale.json()["error_code"]) == (409, "VERSION_CONFLICT")
    bad = client.post(
        f"/api/applications/{app_id}/transitions",
        json={"to_stage": "SUBMITTED", "reason": "nope", "expected_version": 2},
    )
    assert (bad.status_code, bad.json()["error_code"]) == (422, "INVALID_TRANSITION")
    detail_app = client.get(f"/api/applications/{app_id}").json()
    assert [e["to_stage"] for e in detail_app["events"]] == ["DRAFT", "PREPARING"]

    export = client.get("/api/exports/applications.xlsx")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in export.headers["content-disposition"]
    row = read_xlsx(export.content)["Applications"].rows[1]
    assert row[0] == app_id and row[7] == "PREPARING"
    assert client.get("/api/integrity").json()["ok"] is True


def test_changed_source_creates_r2_and_distinct_source_is_suggestion_only(
    client: TestClient,
) -> None:
    first = do_import(client, fixture_bytes("sample-business-manager.txt"))
    r2 = do_import(client, fixture_bytes("sample-business-manager-r2.txt"))
    assert (r2["outcome"], r2["revision_number"], r2["offer_id"]) == (
        "revision_created",
        2,
        first["offer_id"],
    )
    other = do_import(client, fixture_bytes("sample-similar-distinct.txt"))
    assert other["offer_id"] != first["offer_id"] and len(other["duplicate_suggestions"]) == 1
    assert len(client.get("/api/offers").json()) == 2


def test_state_changing_requests_require_the_csrf_header(isolated_data: Path) -> None:
    with TestClient(app) as bare:  # no default X-Requested-With header
        response = bare.post("/api/imports", content=posting())
        assert (response.status_code, response.json()["error_code"]) == (
            403,
            "CSRF_HEADER_REQUIRED",
        )
        assert bare.post("/api/applications", json={"offer_id": "x"}).status_code == 403
        assert bare.get("/api/offers").json() == []  # nothing was written


def test_invalid_uploads_are_rejected_with_typed_errors(client: TestClient) -> None:
    for body, status, code in [
        (b"", 422, "EMPTY_POSTING"),
        (b"Title: \xff\xfe", 422, "NOT_UTF8"),
        (b"Title: a\x00b", 422, "NOT_TEXT"),
        (b"x" * (1024 * 1024 + 1), 413, "POSTING_TOO_LARGE"),
    ]:
        response = client.post("/api/imports", content=body, headers=TEXT)
        assert (response.status_code, response.json()["error_code"]) == (status, code)
    assert client.get("/api/offers").json() == []


def test_unknown_entities_return_404_json(client: TestClient) -> None:
    for path in ("/api/offers/x", "/api/applications/x", "/api/snapshots/x/content"):
        response = client.get(path)
        assert (response.status_code, response.json()["error_code"]) == (404, "NOT_FOUND")


def test_hostile_source_is_served_inert(client: TestClient) -> None:
    raw = posting(title="<script>alert(1)</script>", description="<img src=x onerror=alert(1)>")
    created = do_import(client, raw)
    snapshot = client.get(f"/api/offers/{created['offer_id']}").json()["revisions"][0]["snapshot"]
    response = client.get(f"/api/snapshots/{snapshot['id']}/content")
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in response.headers["content-security-policy"]
    assert "unsafe-inline" not in response.headers["content-security-policy"]


def test_security_headers_on_pages_and_api(client: TestClient) -> None:
    for path in ("/", "/api/offers", "/healthz", "/static/app.js"):
        headers = client.get(path).headers
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["x-frame-options"] == "DENY"
        assert "default-src 'none'" in headers["content-security-policy"]


def test_static_assets_are_allow_listed_and_never_use_html_injection(client: TestClient) -> None:
    script = client.get("/static/app.js")
    assert script.status_code == 200 and "javascript" in script.headers["content-type"]
    assert client.get("/static/app.css").status_code == 200
    for bad in ("../web.py", "..%2fweb.py", "index.html", "missing.js"):
        assert client.get(f"/static/{bad}").status_code == 404
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert forbidden not in script.text
    page = client.get("/").text
    assert "<script src=" in page and "style=" not in page and "onclick=" not in page
    assert page.count("<script") == 1


def test_j0_probes_still_work(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/system/status").json()["database"] == "sqlite"
