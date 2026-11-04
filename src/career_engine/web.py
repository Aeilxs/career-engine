"""Local HTTP surface: J0 probes plus the J1 import / offers / tracker / export API and UI.

Handlers only translate HTTP to the shared use cases in `career_engine.application`.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from importlib.resources import files
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from career_engine import __version__
from career_engine.application import applications, exports, integrity, offers
from career_engine.config import data_directory, database_path_for
from career_engine.db import initialize, read_marker
from career_engine.domain.errors import (
    Conflict,
    DomainError,
    IntegrityFailure,
    InvalidTransition,
    NotFound,
    ValidationFailed,
)
from career_engine.domain.offers import MAX_POSTING_BYTES
from career_engine.infrastructure.jobs import JobQueue

# State-changing requests must carry this header. Browsers cannot attach it cross-origin
# without a CORS preflight, which this app never grants, so other sites cannot drive the API.
REQUIRED_HEADER = ("x-requested-with", "career-engine")
CONTENT_SECURITY_POLICY = (
    "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
    "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ASSETS = {
    "app.js": "text/javascript; charset=utf-8",
    "app.css": "text/css; charset=utf-8",
}


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    initialize(database_path_for(data_directory()))
    # Restart handling: leases left behind by a killed process are requeued or failed.
    JobQueue(database_path_for(data_directory())).reconcile_expired()
    yield


app = FastAPI(title="Career Engine", version=__version__, lifespan=lifespan)


@app.middleware("http")
async def guard(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    if request.method not in {"GET", "HEAD", "OPTIONS"} and (
        request.headers.get(REQUIRED_HEADER[0]) != REQUIRED_HEADER[1]
    ):
        response: Response = JSONResponse(
            {"error_code": "CSRF_HEADER_REQUIRED", "message": "Missing X-Requested-With header."},
            status_code=403,
        )
    else:
        response = await call_next(request)
    response.headers["Content-Security-Policy"] = CONTENT_SECURITY_POLICY
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Cache-Control"] = "no-store"
    return response


_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFound: 404,
    Conflict: 409,
    ValidationFailed: 422,
    InvalidTransition: 422,
    IntegrityFailure: 500,
}


@app.exception_handler(DomainError)
async def domain_error_handler(_: Request, error: DomainError) -> JSONResponse:
    status = 413 if error.code == "POSTING_TOO_LARGE" else _STATUS_BY_ERROR.get(type(error), 400)
    return JSONResponse({"error_code": error.code, "message": error.message}, status_code=status)


@app.get("/healthz")
def health() -> dict[str, str]:
    # Deliberately checks SQLite, not just the existence of the process.
    read_marker(database_path_for(data_directory()))
    return {"status": "ok"}


@app.get("/api/system/status")
def status() -> dict[str, str | None]:
    return {
        "version": __version__,
        "database": "sqlite",
        "marker": read_marker(database_path_for(data_directory())),
    }


def _asset(name: str) -> str:
    return files("career_engine").joinpath("static", name).read_text(encoding="utf-8")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    # No external CDN or runtime fetch: works offline.
    return _asset("index.html")


@app.get("/static/{name}")
def static_asset(name: str) -> Response:
    media_type = _ASSETS.get(name)
    if media_type is None:
        raise NotFound("Unknown asset.")
    return Response(_asset(name), media_type=media_type)


async def _read_body(request: Request) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_POSTING_BYTES:
        raise ValidationFailed("The posting is too large.", "POSTING_TOO_LARGE")
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > MAX_POSTING_BYTES:
            raise ValidationFailed("The posting is too large.", "POSTING_TOO_LARGE")
    return bytes(received)


@app.post("/api/imports")
async def import_offer(
    request: Request,
    source_ref: str | None = None,
    source_id: str | None = None,
    provider: str | None = None,
    board: str | None = None,
) -> JSONResponse:
    """Raw posting bytes in the request body; metadata in query parameters."""
    body = await _read_body(request)
    result = await run_in_threadpool(
        offers.import_posting,
        data_directory(),
        body,
        source_ref=source_ref,
        source_id=source_id,
        provider=provider,
        board=board,
    )
    return JSONResponse(result.to_dict(), status_code=200 if result.outcome == "unchanged" else 201)


@app.get("/api/offers")
def offers_list() -> list[dict[str, Any]]:
    return offers.list_offers(data_directory())


@app.get("/api/offers/{offer_id}")
def offers_detail(offer_id: str) -> dict[str, Any]:
    return offers.get_offer(data_directory(), offer_id)


@app.get("/api/snapshots/{snapshot_id}/content")
def snapshot_content(snapshot_id: str) -> Response:
    # Served as inert plain text; the source bytes are never rendered as HTML.
    return Response(
        offers.read_snapshot(data_directory(), snapshot_id),
        media_type="text/plain; charset=utf-8",
    )


class CreateApplicationBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offer_id: str


class TransitionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to_stage: str
    reason: str
    expected_version: int


@app.post("/api/applications", status_code=201)
def application_create(body: CreateApplicationBody) -> dict[str, Any]:
    return applications.create_application(data_directory(), body.offer_id)


@app.get("/api/applications")
def application_list() -> list[dict[str, Any]]:
    return applications.list_applications(data_directory())


@app.get("/api/applications/{application_id}")
def application_detail(application_id: str) -> dict[str, Any]:
    return applications.get_application(data_directory(), application_id)


@app.post("/api/applications/{application_id}/transitions")
def application_transition(application_id: str, body: TransitionBody) -> dict[str, Any]:
    return applications.transition_application(
        data_directory(), application_id, body.to_stage, body.reason, body.expected_version
    )


@app.get("/api/exports/applications.xlsx")
def export_xlsx() -> Response:
    payload = exports.build_applications_workbook(data_directory())
    return Response(
        payload,
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="applications.xlsx"'},
    )


@app.get("/api/integrity")
def integrity_report() -> dict[str, Any]:
    return integrity.verify_integrity(data_directory())
