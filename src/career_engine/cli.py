"""Deliberately small CLI for J0 verification and future automation."""

import argparse
import json
from collections.abc import Sequence

import uvicorn

from career_engine import __version__
from career_engine.config import database_path
from career_engine.db import initialize, read_marker, write_marker


def main(argv: Sequence[str] | None = None) -> int:
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
    args = parser.parse_args(argv)

    if args.command == "serve":
        uvicorn.run("career_engine.web:app", host=args.host, port=args.port, workers=1)
        return 0

    initialize()
    if args.command == "doctor":
        print(json.dumps({"ok": True, "database_path": str(database_path())}))
        return 0
    if args.marker_command == "set":
        write_marker(args.value)
    print(json.dumps({"marker": read_marker()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
