"""Real process kill/restart: records and hashes survive SIGKILL of the actual server process."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from helpers import fixture_bytes
from xlsx_reader import read_xlsx

from career_engine.infrastructure.objects import sha256_hex

HEADERS = {"X-Requested-With": "career-engine"}


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def call(
    port: int, path: str, *, method: str = "GET", body: bytes | None = None, json_body: Any = None
) -> tuple[int, bytes]:
    headers = dict(HEADERS)
    if json_body is not None:
        body = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body, headers=headers, method=method
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, response.read()


class Server:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir, self.port = data_dir, free_port()
        self.process: subprocess.Popen[bytes] | None = None

    def start(self) -> None:
        env = {**os.environ, "CAREER_DATA_DIR": str(self.data_dir)}
        self.process = subprocess.Popen(
            [sys.executable, "-m", "career_engine.cli", "serve", "--port", str(self.port)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                if call(self.port, "/healthz")[0] == 200:
                    return
            except OSError:
                time.sleep(0.1)
        raise AssertionError("server did not become healthy")

    def kill(self) -> None:
        assert self.process is not None
        self.process.kill()  # SIGKILL: no graceful shutdown
        self.process.wait(timeout=10)
        assert self.process.returncode != 0


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Server]:
    instance = Server(tmp_path)
    yield instance
    if instance.process is not None and instance.process.poll() is None:
        instance.process.kill()
        instance.process.wait(timeout=10)


def test_records_and_hashes_survive_sigkill_restart(server: Server) -> None:
    raw = fixture_bytes("sample-business-manager.txt")
    server.start()
    _, body = call(server.port, "/api/imports?source_ref=restart-test", method="POST", body=raw)
    imported = json.loads(body)
    _, body = call(
        server.port,
        "/api/applications",
        method="POST",
        json_body={"offer_id": imported["offer_id"]},
    )
    application = json.loads(body)
    call(
        server.port,
        f"/api/applications/{application['id']}/transitions",
        method="POST",
        json_body={"to_stage": "PREPARING", "reason": "before kill", "expected_version": 1},
    )
    server.kill()

    server.start()
    _, body = call(server.port, f"/api/offers/{imported['offer_id']}")
    revision = json.loads(body)["revisions"][0]
    assert revision["snapshot"]["content_sha256"] == sha256_hex(raw)
    _, source = call(server.port, f"/api/snapshots/{revision['snapshot']['id']}/content")
    assert source == raw
    _, body = call(server.port, f"/api/applications/{application['id']}")
    restored = json.loads(body)
    assert (restored["stage"], restored["version"]) == ("PREPARING", 2)
    assert [e["to_stage"] for e in restored["events"]] == ["DRAFT", "PREPARING"]
    assert json.loads(call(server.port, "/api/integrity")[1])["ok"] is True
    status, again = call(server.port, "/api/imports", method="POST", body=raw)
    assert status == 200 and json.loads(again)["outcome"] == "unchanged"
    _, workbook = call(server.port, "/api/exports/applications.xlsx")
    assert read_xlsx(workbook)["Applications"].rows[1][0] == application["id"]
