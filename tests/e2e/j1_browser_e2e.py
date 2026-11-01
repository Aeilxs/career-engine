# ruff: noqa: E501
"""J1 `manual-ingest-to-xlsx` real-browser E2E (opt-in; not collected by the default pytest run).

Drives the real UI in a real Chromium-family browser against a real server with an isolated
throwaway data directory, kills/restarts the server, and compares UI, SQL, object files and the
exported XLSX. Offline: only a local server and synthetic fixtures are used.

Run (no project dependency is added; tools are resolved ephemerally by uv):

    uv run --frozen --with playwright --with openpyxl python tests/e2e/j1_browser_e2e.py
    uv run --frozen --with playwright --with openpyxl python tests/e2e/j1_browser_e2e.py --mode docker

`--mode process` SIGKILLs and restarts `career serve`; `--mode docker` uses the repository's
compose.yaml unmodified plus a generated throwaway override (project name, data dir, port) and
restarts the container with `docker compose down` / `up`.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "offers"
BROWSERS = [
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]
RESULTS: list[dict[str, Any]] = []
COMMANDS: list[dict[str, Any]] = []


def check(name: str, condition: bool, detail: Any = None) -> None:
    RESULTS.append({"check": name, "passed": bool(condition), "detail": detail})
    print(("PASS " if condition else "FAIL ") + name + ("" if condition else f"  -> {detail!r}"))


def passes(name: str, assertion: Callable[[], None]) -> None:
    try:
        assertion()
    except AssertionError as error:
        check(name, False, str(error)[:300])
    else:
        check(name, True)


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True, **kwargs)
    COMMANDS.append({"command": " ".join(command), "exit_code": completed.returncode})
    return completed


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_healthy(port: int, timeout: float = 90) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError("server did not become healthy")


class ProcessServer:
    """`career serve` as a child process; restart = SIGKILL + start."""

    mode = "process"

    def __init__(self, workdir: Path) -> None:
        self.data_dir = workdir / "data"
        self.data_dir.mkdir()
        self.port = free_port()
        self.process: subprocess.Popen[bytes] | None = None

    @property
    def env(self) -> dict[str, str]:
        return {**os.environ, "CAREER_DATA_DIR": str(self.data_dir)}

    def start(self) -> None:
        self.process = subprocess.Popen(
            [sys.executable, "-m", "career_engine.cli", "serve", "--port", str(self.port)],
            env=self.env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        COMMANDS.append({"command": f"career serve --port {self.port}", "exit_code": None})
        wait_healthy(self.port)

    def stop_hard(self) -> int:
        assert self.process is not None
        self.process.kill()
        code = self.process.wait(timeout=10)
        COMMANDS.append({"command": "SIGKILL career serve", "exit_code": code})
        return code

    def restart(self) -> None:
        self.stop_hard()
        self.start()

    def query(self, sql: str) -> list[tuple[Any, ...]]:
        connection = sqlite3.connect(f"file:{self.data_dir / 'career.db'}?mode=ro", uri=True)
        try:
            return connection.execute(sql).fetchall()
        finally:
            connection.close()

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run([sys.executable, "-m", "career_engine.cli", *args], env=self.env)

    def shutdown(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=10)


class DockerServer:
    """The repository's one-service compose app, isolated by project name, data dir and port."""

    mode = "docker"

    def __init__(self, workdir: Path) -> None:
        self.data_dir = workdir / "data"
        self.data_dir.mkdir()
        self.port = free_port()
        override = workdir / "compose.e2e.yaml"
        override.write_text(
            "services:\n  app:\n    volumes: !override\n"
            f"      - {self.data_dir}:/data\n    ports: !override\n"
            f'      - "127.0.0.1:{self.port}:8000"\n'
        )
        self.base = [
            "docker",
            "compose",
            "-p",
            "career-e2e-j1",
            "-f",
            str(ROOT / "compose.yaml"),
            "-f",
            str(override),
        ]
        self.env = {**os.environ, "CAREER_UID": str(os.getuid()), "CAREER_GID": str(os.getgid())}

    def compose(self, *args: str) -> subprocess.CompletedProcess[str]:
        return run([*self.base, *args], env=self.env, cwd=ROOT)

    def start(self) -> None:
        result = self.compose("up", "--build", "-d", "--wait")
        if result.returncode != 0:
            raise RuntimeError(result.stdout + result.stderr)
        wait_healthy(self.port)

    def stop_hard(self) -> int:
        return self.compose("down").returncode

    def restart(self) -> None:
        # Container is destroyed and recreated; only the bind-mounted data survives.
        assert self.stop_hard() == 0
        self.start()

    def query(self, sql: str) -> list[tuple[Any, ...]]:
        # Never open a WAL database across the VM boundary from the host: query inside the container.
        script = (
            "import json,sqlite3;c=sqlite3.connect('file:/data/career.db?mode=ro',uri=True);"
            f"print(json.dumps(c.execute({sql!r}).fetchall()))"
        )
        result = self.compose("exec", "-T", "app", "python", "-c", script)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        return [tuple(row) for row in json.loads(result.stdout)]

    def cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return self.compose("exec", "-T", "app", "career", *args)

    def shutdown(self) -> None:
        self.compose("down")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_counts(server: Any) -> dict[str, int]:
    tables = [
        "offer",
        "offer_revision",
        "source_snapshot",
        "application",
        "application_event",
        "duplicate_suggestion",
    ]
    return {t: int(server.query(f"SELECT COUNT(*) FROM {t}")[0][0]) for t in tables}


def wait_outcome(page: Page) -> str:
    page.wait_for_selector("#import-result:not([hidden]), #error:not([hidden])")
    if page.is_visible("#error"):
        return "error: " + page.inner_text("#error")
    return page.inner_text("#import-result h3")


def import_text(page: Page, text: str, label: str, source_id: str | None = None) -> str:
    page.click("#tab-import")
    page.set_input_files("#posting-file", [])
    page.fill("#posting-text", text)
    page.fill("#source-ref", label)
    if not page.locator("details").evaluate("node => node.open"):
        page.click("details summary")
    page.fill("#source-id", source_id or "")
    page.click("#import-button")
    return wait_outcome(page)


def read_export(page: Page, destination: Path) -> Path:
    page.click("#tab-tracker")
    with page.expect_download() as download:
        page.click("#export-link")
    download.value.save_as(destination)
    return destination


def compare_export_to_sql(server: Any, workbook_path: Path, label: str) -> None:
    sql = server.query(
        "SELECT a.id, a.offer_id, r.company, r.title, r.locations_json, r.apply_url, o.created_at,"
        " a.stage, r.revision_number, a.dossier_path FROM application a"
        " JOIN offer o ON o.id = a.offer_id JOIN offer_revision r ON r.id = a.offer_revision_id"
        " ORDER BY a.created_at, a.rowid"
    )
    sheet = load_workbook(workbook_path)["Applications"]
    rows = list(sheet.iter_rows(min_row=2, values_only=True))
    check(
        f"{label}: XLSX row count equals SQL application count",
        len(rows) == len(sql),
        [len(rows), len(sql)],
    )
    for row, record in zip(rows, sql, strict=False):
        locations = json.loads(record[4]) if record[4] else None
        expected = (
            record[0],
            record[1],
            record[2],
            record[3],
            "; ".join(locations) if locations else None,
            record[5],
            datetime.fromisoformat(record[6]).astimezone(UTC).replace(tzinfo=None),
            record[7],
            None,
            record[8],
            None,
            None,
            None,
            None,
            record[9],
        )
        check(
            f"{label}: XLSX row {record[0][:8]} equals SQL", tuple(row) == expected, [row, expected]
        )
    header = [c.value for c in sheet[1]]
    check(
        f"{label}: contract header columns",
        header[:3] == ["application_id", "offer_id", "company"] and len(header) == 15,
        header,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["process", "docker"], default="process")
    parser.add_argument("--browser", default=os.environ.get("E2E_BROWSER"))
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    artifacts = ROOT / "reports" / "artifacts" / f"J1-{args.mode}-{stamp}"
    artifacts.mkdir(parents=True)
    browser_path = args.browser or next((p for p in BROWSERS if Path(p).exists()), None)

    # Colima/Docker Desktop only share $HOME with the VM; /var/folders is not bind-mountable.
    scratch_root = Path.home() / ".cache" / "career-engine-e2e" if args.mode == "docker" else None
    if scratch_root is not None:
        scratch_root.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="career-e2e-j1-", dir=scratch_root))
    server: Any = (DockerServer if args.mode == "docker" else ProcessServer)(workdir)
    summary: dict[str, Any] = {
        "milestone": "J1",
        "mode": args.mode,
        "started_utc": stamp,
        "git_sha": run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip(),
        "git_dirty": bool(run(["git", "status", "--porcelain"], cwd=ROOT).stdout.strip()),
        "host": platform.platform(),
        "python": sys.version.split()[0],
        "browser": browser_path or "playwright-managed chromium",
    }
    manager = f"http://127.0.0.1:{server.port}"
    business = (FIXTURES / "sample-business-manager.txt").read_text(encoding="utf-8")
    business_r2 = FIXTURES / "sample-business-manager-r2.txt"
    similar = (FIXTURES / "sample-similar-distinct.txt").read_text(encoding="utf-8")
    formula = (
        "Title: =1+1\nCompany: +Evil Corp (synthetic)\nSource ID: synthetic/board/formula-001\n"
        "Description: Formula-like external strings must stay inert text.\n"
    )
    failure: str | None = None

    try:
        server.start()
        with sync_playwright() as playwright:
            launch: dict[str, Any] = {"headless": not args.headed}
            if browser_path:
                launch["executable_path"] = browser_path
            browser = playwright.chromium.launch(**launch)
            summary["browser_version"] = browser.version
            context = browser.new_context(
                accept_downloads=True, viewport={"width": 1280, "height": 900}
            )
            page = context.new_page()
            page_errors: list[str] = []
            failed_requests: list[tuple[int, str]] = []

            def watch(watched: Page) -> None:
                watched.on("pageerror", lambda error: page_errors.append(str(error)))
                watched.on(
                    "response",
                    lambda r: (
                        failed_requests.append((r.status, r.url.removeprefix(manager)))
                        if r.status >= 400
                        else None
                    ),
                )

            watch(page)
            page.goto(manager + "/")

            # 1. Import a synthetic posting through the browser.
            outcome = import_text(page, business, "e2e-business-manager.txt")
            check(
                "1: first import reports a new offer",
                outcome.startswith("New offer created"),
                outcome,
            )
            page.screenshot(path=str(artifacts / "01-import-result.png"))
            counts = table_counts(server)
            check(
                "1: SQL has 1 offer, 1 revision, 1 snapshot, 0 applications",
                (
                    counts["offer"],
                    counts["offer_revision"],
                    counts["source_snapshot"],
                    counts["application"],
                )
                == (1, 1, 1, 0),
                counts,
            )

            # 2. Provenance, normalized fields, offer vs application separation.
            page.click("#open-imported-offer")
            page.wait_for_selector("#offer-fields")

            def cell(field: str, col: int) -> str:
                return page.inner_text(f"#offer-fields tr[data-field={field}] td:nth-child({col})")

            check(
                "2: title normalized",
                cell("title", 2) == "Business Manager — Industrial Energy",
                cell("title", 2),
            )
            check(
                "2: company normalized",
                cell("company", 2) == "Example Industrial Solutions (synthetic)",
            )
            check("2: location normalized", cell("locations", 2) == "Marseille, France")
            check("2: contract normalized", cell("contract", 2) == "Permanent")
            check(
                "2: apply URL normalized",
                cell("apply_url", 2) == "https://example.org/jobs/offer-001",
            )
            check(
                "2: field provenance shows source offsets",
                cell("title", 3).startswith("source characters "),
                cell("title", 3),
            )
            page.click("button.view-source")
            page.wait_for_selector("#source-view:not([hidden])")
            check(
                "2: source view equals the imported bytes",
                page.inner_text("#source-view").strip() == business.strip(),
            )
            check(
                "2: no application exists yet (offer != application)",
                page.is_visible("#create-application") and table_counts(server)["application"] == 0,
            )
            page.screenshot(path=str(artifacts / "02-offer-detail.png"))
            snapshot = server.query(
                "SELECT content_sha256, object_ref, size_bytes FROM source_snapshot"
            )[0]
            check(
                "2: snapshot hash equals SHA-256 of the fixture bytes",
                snapshot[0] == hashlib.sha256(business.encode("utf-8")).hexdigest(),
                snapshot,
            )

            # 3. Reimport 10 times -> still one offer/revision; changed file -> R2; similar -> separate offer.
            outcomes = [import_text(page, business, "e2e-business-manager.txt") for _ in range(10)]
            check(
                "3: 10 reimports all report 'nothing new stored'",
                all(o.startswith("Identical to the current revision") for o in outcomes),
                outcomes,
            )
            counts = table_counts(server)
            check(
                "3: still 1 offer / 1 revision / 1 snapshot after 10 reimports",
                (counts["offer"], counts["offer_revision"], counts["source_snapshot"]) == (1, 1, 1),
                counts,
            )
            page.click("#tab-import")
            page.fill("#posting-text", "")
            page.set_input_files("#posting-file", str(business_r2))
            page.click("#import-button")
            outcome = wait_outcome(page)
            check(
                "3: changed source (file upload) creates revision 2",
                "new revision 2" in outcome,
                outcome,
            )
            counts = table_counts(server)
            check(
                "3: SQL has 1 offer and 2 revisions",
                (counts["offer"], counts["offer_revision"]) == (1, 2),
                counts,
            )
            outcome = import_text(page, similar, "e2e-similar.txt")
            check(
                "3: similar title from a distinct source is a new offer",
                outcome.startswith("New offer created"),
                outcome,
            )
            page.wait_for_selector("#duplicate-suggestions li")
            check(
                "3: duplicate suggestion shown in UI, no merge",
                page.locator("#duplicate-suggestions li").count() == 1,
            )
            page.screenshot(path=str(artifacts / "03-duplicate-suggestion.png"))
            counts = table_counts(server)
            check(
                "3: SQL has 2 offers, 3 revisions, 1 suggestion",
                (counts["offer"], counts["offer_revision"], counts["duplicate_suggestion"])
                == (2, 3, 1),
                counts,
            )

            # 6 (early). Formula-like title is stored and later exported as inert text.
            outcome = import_text(page, formula, "e2e-formula.txt")
            check(
                "6: formula-like posting imported", outcome.startswith("New offer created"), outcome
            )
            check(
                "6: SQL stores the formula-like title verbatim",
                server.query("SELECT title FROM offer_revision WHERE title LIKE '=%'")
                == [("=1+1",)],
            )

            # Error handling in the UI without writing anything.
            before = table_counts(server)
            page.click("#tab-import")
            page.fill("#posting-text", "")
            page.set_input_files("#posting-file", [])
            page.click("#import-button")
            check(
                "5: empty submission shows an error",
                page.inner_text("#error").startswith("Provide posting text"),
            )
            check("5: rejected submission leaves SQL unchanged", table_counts(server) == before)

            # 4. Application creation, status update with a transactional event.
            page.click("#tab-offers")
            expect(page.locator("#offers-table tbody tr")).to_have_count(3)
            check(
                "4: offers list shows 3 offers", page.locator("#offers-table tbody tr").count() == 3
            )
            for title in ("Business Manager — Industrial Energy", "=1+1"):
                page.click("#tab-offers")
                expect(page.locator("#offers-table tbody tr")).to_have_count(3)
                row = page.locator("#offers-table tbody tr", has_text=title).first
                row.locator("button.open-offer").click()
                page.wait_for_selector("#create-application")
                page.click("#create-application")
                page.wait_for_selector("#application-stage")
            counts = table_counts(server)
            check(
                "4: 2 applications and 2 CREATED events",
                (counts["application"], counts["application_event"]) == (2, 2),
                counts,
            )
            page.click("#tab-offers")
            page.locator("#offers-table tbody tr", has_text="Business Manager").first.locator(
                "button.open-offer"
            ).click()
            page.wait_for_selector("#application-exists")
            check(
                "4: offer detail reports the existing application",
                "Application exists" in page.inner_text("#application-exists"),
            )
            page.click("#tab-tracker")
            page.wait_for_selector("#tracker-table tbody tr")
            page.locator("#tracker-table tbody tr", has_text="Business Manager").locator(
                "button.open-application"
            ).click()
            page.wait_for_selector("#transition-button")
            page.click("#transition-button")
            passes(
                "4: status update without reason is refused (UI error shown)",
                lambda: expect(page.locator("#error")).to_contain_text("INVALID_REASON"),
            )
            check(
                "4: refused update changed nothing", table_counts(server)["application_event"] == 2
            )
            page.select_option("#transition-stage", "PREPARING")
            page.fill("#transition-reason", "Start preparing the application")
            page.click("#transition-button")
            expect(page.locator("#application-stage")).to_have_text("PREPARING")
            events = server.query(
                "SELECT e.from_stage, e.to_stage, e.actor, e.reason, e.resulting_version FROM application_event e"
                " JOIN application a ON a.id = e.application_id WHERE a.stage = 'PREPARING' ORDER BY e.rowid"
            )
            check(
                "4: SQL has CREATED + STAGE_CHANGED event with actor and reason",
                events[-1]
                == ("DRAFT", "PREPARING", "local-user", "Start preparing the application", 2),
                events,
            )
            page.screenshot(path=str(artifacts / "04-tracker.png"))

            # 4/6. XLSX export compared with SQL; formula text stays text.
            first_export = read_export(page, artifacts / "applications-before-restart.xlsx")
            compare_export_to_sql(server, first_export, "export")
            sheet = load_workbook(first_export)["Applications"]
            titles = {r[3].value: r[3] for r in sheet.iter_rows(min_row=2)}
            check(
                "6: formula-like title exported as a string cell, not a formula",
                titles["=1+1"].data_type == "s"
                and titles["=1+1"].value == "=1+1"
                and titles["=1+1"].quotePrefix,
                [titles["=1+1"].data_type, titles["=1+1"].value],
            )
            check(
                "6: no formula cell exists anywhere in the workbook",
                all(
                    c.data_type != "f"
                    for ws in load_workbook(first_export)
                    for r in ws.iter_rows()
                    for c in r
                ),
            )
            check(
                "4: imported_at is a typed date cell",
                isinstance(sheet["G2"].value, datetime),
                sheet["G2"].value,
            )
            check("4: autofilter present", sheet.auto_filter.ref == "A1:O3", sheet.auto_filter.ref)

            # 5. Missing file through the CLI: nonzero exit, nothing written.
            before = table_counts(server)
            missing = server.cli("ingest", "--file", "/definitely/not/here.txt")
            check(
                "5: ingest of a missing file exits nonzero",
                missing.returncode != 0,
                missing.returncode,
            )
            check("5: missing file left SQL untouched", table_counts(server) == before)

            # 5. Restart and verify records + artifact hashes.
            before = table_counts(server)
            snapshots_before = server.query(
                "SELECT id, content_sha256, object_ref FROM source_snapshot ORDER BY id"
            )
            application_rows_before = server.query(
                "SELECT id, stage, version, manifest_sha256 FROM application ORDER BY id"
            )
            summary["counts_before_restart"] = before
            context.close()
            marker = f"j0-regression-{stamp}"
            marker_set = server.cli("marker", "set", marker)
            check("J0 regression: marker written", marker_set.returncode == 0, marker_set.stderr)
            server.stop_hard()
            hashes_ok = all(
                sha256_file(server.data_dir / ref) == sha for _, sha, ref in snapshots_before
            )
            check("5: object files on disk match stored SHA-256 while server is down", hashes_ok)
            check(
                "5: application manifests on disk match stored SHA-256",
                all(
                    sha256_file(server.data_dir / "applications" / app_id / "manifest.json")
                    == manifest
                    for app_id, _, _, manifest in application_rows_before
                ),
            )
            server.start()
            marker_get = server.cli("marker", "get")
            check(
                "J0 regression: marker survived the restart",
                marker_get.returncode == 0 and marker in marker_get.stdout,
                marker_get.stdout,
            )
            with urllib.request.urlopen(f"{manager}/api/system/status") as response:
                check(
                    "J0 regression: status endpoint shows marker",
                    marker in response.read().decode(),
                )
            check(
                "5: restart: same row counts", table_counts(server) == before, table_counts(server)
            )
            check(
                "5: restart: same snapshots",
                server.query(
                    "SELECT id, content_sha256, object_ref FROM source_snapshot ORDER BY id"
                )
                == snapshots_before,
            )
            check(
                "5: restart: same application state",
                server.query(
                    "SELECT id, stage, version, manifest_sha256 FROM application ORDER BY id"
                )
                == application_rows_before,
            )
            with urllib.request.urlopen(f"{manager}/api/integrity") as response:
                report = json.loads(response.read())
            check(
                "5: integrity report ok after restart",
                report["ok"] and report["objects_checked"] == len(snapshots_before),
                report,
            )
            summary["integrity_after_restart"] = report

            context = browser.new_context(
                accept_downloads=True, viewport={"width": 1280, "height": 900}
            )
            page = context.new_page()
            watch(page)
            page.goto(manager + "/")
            page.click("#tab-tracker")
            page.wait_for_selector("#tracker-table tbody tr")
            check(
                "5: tracker shows both applications after restart",
                page.locator("#tracker-table tbody tr").count() == 2,
            )
            check(
                "5: stage survived restart in the UI",
                "PREPARING" in page.inner_text("#tracker-table"),
            )
            page.screenshot(path=str(artifacts / "05-tracker-after-restart.png"))
            second_export = read_export(page, artifacts / "applications-after-restart.xlsx")
            compare_export_to_sql(server, second_export, "export after restart")
            page.click("#tab-import")
            outcome = import_text(page, business_r2.read_text(encoding="utf-8"), "e2e-r2.txt")
            check(
                "5: reimport after restart is still unchanged (no duplicate)",
                "nothing new stored" in outcome,
                outcome,
            )
            app_id = server.query(
                "SELECT a.id FROM application a JOIN offer_revision r ON r.id = a.offer_revision_id"
                " WHERE r.title LIKE 'Business Manager%'"
            )[0][0]
            expected_failures = [(422, f"/api/applications/{app_id}/transitions")]
            unexpected = [f for f in failed_requests if f != (404, "/favicon.ico")]
            check("UI: no uncaught page errors", page_errors == [], page_errors)
            check(
                "UI: only the deliberate empty-reason 422 (and a browser favicon probe) failed",
                unexpected == expected_failures,
                failed_requests,
            )
            context.close()
            browser.close()
        summary["final_counts"] = table_counts(server)
        summary["snapshot_hashes"] = server.query(
            "SELECT id, content_sha256 FROM source_snapshot ORDER BY id"
        )
    except Exception as error:  # record, then fail the run
        failure = f"{type(error).__name__}: {error}"
        check("E2E ran to completion", False, failure)
    finally:
        server.shutdown()
        shutil.rmtree(workdir, ignore_errors=True)

    failed = [r for r in RESULTS if not r["passed"]]
    summary.update(
        passed=len(RESULTS) - len(failed),
        failed=len(failed),
        failure=failure,
        results=RESULTS,
        commands=COMMANDS,
    )
    (artifacts / "e2e-result.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\n{summary['passed']} passed, {summary['failed']} failed; artifacts: {artifacts}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
