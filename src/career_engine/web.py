"""Local J0 HTTP surface, including a visible front page."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from career_engine import __version__
from career_engine.db import initialize, read_marker


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize()
    yield


app = FastAPI(title="Career Engine", version=__version__, lifespan=lifespan)


@app.get("/healthz")
def health() -> dict[str, str]:
    # Deliberately checks SQLite, not just the existence of the process.
    read_marker()
    return {"status": "ok"}


@app.get("/api/system/status")
def status() -> dict[str, str | None]:
    return {"version": __version__, "database": "sqlite", "marker": read_marker()}


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    # No external CDN or runtime fetch: works offline.
    return files("career_engine").joinpath("static", "index.html").read_text(encoding="utf-8")
