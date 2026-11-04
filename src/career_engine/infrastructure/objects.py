"""Content-addressed immutable objects and atomic file writes under the data directory.

Protocol: write to a temporary file in the destination directory, flush + fsync, atomically
rename, then (in the caller) commit SQL references. DB and files are not one atomic unit:
an interruption can leave an unreferenced object, which `verify_integrity` reports.
"""

import hashlib
import os
import re
import uuid
from pathlib import Path

from career_engine.domain.errors import IntegrityFailure

_REF_PATTERN = re.compile(r"^objects/sha256/[0-9a-f]{2}/[0-9a-f]{64}$")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    try:
        with open(temporary, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    _fsync_directory(path.parent)


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


class ObjectStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir

    @staticmethod
    def ref_for(sha256: str) -> str:
        return f"objects/sha256/{sha256[:2]}/{sha256}"

    def path(self, ref: str) -> Path:
        if not _REF_PATTERN.fullmatch(ref):
            raise IntegrityFailure(f"Malformed object reference: {ref!r}", "BAD_OBJECT_REF")
        return self.root / ref

    def put(self, data: bytes) -> tuple[str, str]:
        """Store bytes idempotently; also repairs a missing or corrupted object file."""
        digest = sha256_hex(data)
        ref = self.ref_for(digest)
        target = self.path(ref)
        if target.is_file() and sha256_hex(target.read_bytes()) == digest:
            return digest, ref
        atomic_write_bytes(target, data)
        return digest, ref

    def read_verified(self, ref: str, expected_sha256: str) -> bytes:
        target = self.path(ref)
        try:
            data = target.read_bytes()
        except FileNotFoundError as error:
            raise IntegrityFailure(f"Object file missing: {ref}", "OBJECT_MISSING") from error
        if sha256_hex(data) != expected_sha256:
            raise IntegrityFailure(f"Object hash mismatch: {ref}", "OBJECT_CORRUPT")
        return data
