"""CLI over the same use cases as the HTTP API. Output is JSON; see exit codes below.

Exit codes: 0 success, 1 internal/integrity failure, 2 bad input or unknown entity,
3 conflict, 4 blocked transition, 5 uncertain external outcome (unused before J6).
"""

import argparse
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import uvicorn

from career_engine import __version__
from career_engine.application import applications, exports, integrity, offers
from career_engine.application.worker import run_once
from career_engine.config import data_directory, database_path, database_path_for
from career_engine.db import initialize, read_marker, write_marker
from career_engine.domain.errors import (
    Conflict,
    DomainError,
    IntegrityFailure,
    InvalidTransition,
    NotFound,
    ValidationFailed,
)
from career_engine.infrastructure.jobs import JobQueue

EXIT_BY_ERROR: dict[type[DomainError], int] = {
    ValidationFailed: 2,
    NotFound: 2,
    Conflict: 3,
    InvalidTransition: 4,
    IntegrityFailure: 1,
}
CLI_ACTOR = "cli"


def _emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _fail(code: str, message: str, exit_code: int) -> int:
    print(json.dumps({"status": "error", "error_code": code, "message": message}), file=sys.stderr)
    return exit_code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="career")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check persistent SQLite access")
    marker = commands.add_parser("marker", help="J0 durability-only smoke marker")
    marker_commands = marker.add_subparsers(dest="marker_command", required=True)
    marker_commands.add_parser("get")
    setter = marker_commands.add_parser("set")
    setter.add_argument("value")
    serve = commands.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    ingest = commands.add_parser("ingest", help="Import a text posting from a file")
    ingest.add_argument("--file", required=True, type=Path)
    ingest.add_argument("--source-ref")
    ingest.add_argument("--source-id")
    ingest.add_argument("--provider")
    ingest.add_argument("--board")

    offer = commands.add_parser("offers", help="Inspect imported offers")
    offer_commands = offer.add_subparsers(dest="offers_command", required=True)
    offer_commands.add_parser("list")
    show = offer_commands.add_parser("show")
    show.add_argument("offer_id")

    application = commands.add_parser("application", help="Create and track applications")
    application_commands = application.add_subparsers(dest="application_command", required=True)
    create = application_commands.add_parser("create")
    create.add_argument("--offer", required=True)
    application_commands.add_parser("list")
    transition = application_commands.add_parser("transition")
    transition.add_argument("application_id")
    transition.add_argument("--to", required=True, dest="to_stage")
    transition.add_argument("--reason", required=True)
    transition.add_argument("--expected-version", required=True, type=int)

    export = commands.add_parser("export", help="Write the tracker projection")
    export.add_argument("--format", choices=["xlsx"], required=True)
    export.add_argument("--output", required=True, type=Path)

    commands.add_parser("verify", help="Verify object and manifest hashes against SQL")
    worker = commands.add_parser("worker", help="Durable job-claim loop (no job kinds in J1)")
    worker.add_argument("--once", action="store_true")
    worker.add_argument("--poll-seconds", type=float, default=2.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if args.command == "serve":
        uvicorn.run("career_engine.web:app", host=args.host, port=args.port, workers=1)
        return 0

    try:
        return _dispatch(args)
    except DomainError as error:
        return _fail(error.code, error.message, EXIT_BY_ERROR.get(type(error), 1))
    except OSError as error:
        return _fail("FILE_ERROR", f"{type(error).__name__}: {error.strerror or error}", 2)


def _dispatch(args: argparse.Namespace) -> int:
    initialize(database_path())
    data_dir = data_directory()

    if args.command == "doctor":
        _emit({"ok": True, "database_path": str(database_path())})
    elif args.command == "marker":
        if args.marker_command == "set":
            write_marker(args.value)
        _emit({"marker": read_marker()})
    elif args.command == "ingest":
        raw = args.file.read_bytes()
        result = offers.import_posting(
            data_dir,
            raw,
            source_ref=args.source_ref or args.file.name,
            source_id=args.source_id,
            provider=args.provider,
            board=args.board,
        )
        _emit({"status": "ok", **result.to_dict()})
    elif args.command == "offers":
        if args.offers_command == "list":
            _emit(offers.list_offers(data_dir))
        else:
            _emit(offers.get_offer(data_dir, args.offer_id))
    elif args.command == "application":
        if args.application_command == "create":
            _emit(applications.create_application(data_dir, args.offer, actor=CLI_ACTOR))
        elif args.application_command == "list":
            _emit(applications.list_applications(data_dir))
        else:
            _emit(
                applications.transition_application(
                    data_dir,
                    args.application_id,
                    args.to_stage,
                    args.reason,
                    args.expected_version,
                    actor=CLI_ACTOR,
                )
            )
    elif args.command == "export":
        size = exports.write_applications_export(data_dir, args.output)
        _emit({"status": "ok", "output": str(args.output), "bytes": size})
    elif args.command == "verify":
        report = integrity.verify_integrity(data_dir)
        _emit(report)
        return 0 if report["ok"] else 1
    elif args.command == "worker":
        queue = JobQueue(database_path_for(data_dir))
        while True:
            outcome = run_once(queue, {})
            if args.once:
                _emit({"status": "ok", "outcome": outcome})
                return 0
            if outcome == "IDLE":
                time.sleep(args.poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
