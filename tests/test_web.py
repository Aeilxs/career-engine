from pathlib import Path

from fastapi.testclient import TestClient

from career_engine.db import write_marker
from career_engine.web import app


def test_health_and_home_from_real_sqlite(isolated_data: Path) -> None:
    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        home = client.get("/")
        assert home.status_code == 200
        assert "Career Engine" in home.text
        write_marker("visible-J0")
        state = client.get("/api/system/status").json()
        assert state == {"version": "0.1.0", "database": "sqlite", "marker": "visible-J0"}
    assert (isolated_data / "career.db").is_file()
