"""Verify stored objects and application manifests against SQL hashes."""

import re
from contextlib import closing
from pathlib import Path
from typing import Any

from career_engine.config import database_path_for
from career_engine.db import connect
from career_engine.domain.errors import IntegrityFailure
from career_engine.infrastructure.objects import ObjectStore, sha256_hex

_OBJECT_NAME = re.compile(r"^[0-9a-f]{64}$")


def verify_integrity(data_dir: Path) -> dict[str, Any]:
    """Report missing/corrupt files (failures) and unreferenced files (orphans, never deleted)."""
    store = ObjectStore(data_dir)
    missing: list[str] = []
    corrupt: list[str] = []
    with closing(connect(database_path_for(data_dir))) as connection:
        snapshots = connection.execute(
            "SELECT id, object_ref, content_sha256 FROM source_snapshot"
        ).fetchall()
        applications = connection.execute(
            "SELECT id, dossier_path, manifest_sha256 FROM application"
        ).fetchall()
    referenced_objects = {str(row["object_ref"]) for row in snapshots}
    known_applications = {str(row["id"]) for row in applications}

    for row in snapshots:
        try:
            store.read_verified(str(row["object_ref"]), str(row["content_sha256"]))
        except IntegrityFailure as error:
            (missing if error.code == "OBJECT_MISSING" else corrupt).append(str(row["object_ref"]))
    for row in applications:
        manifest = data_dir / str(row["dossier_path"]) / "manifest.json"
        label = f"{row['dossier_path']}/manifest.json"
        if not manifest.is_file():
            missing.append(label)
        elif sha256_hex(manifest.read_bytes()) != row["manifest_sha256"]:
            corrupt.append(label)

    orphan_objects = sorted(
        str(path.relative_to(data_dir))
        for path in (data_dir / "objects").glob("sha256/*/*")
        if _OBJECT_NAME.fullmatch(path.name)
        and str(path.relative_to(data_dir)) not in referenced_objects
    )
    orphan_dossiers = sorted(
        f"applications/{path.name}"
        for path in (data_dir / "applications").glob("*")
        if path.is_dir() and path.name not in known_applications
    )
    temporary_files = sorted(
        str(path.relative_to(data_dir))
        for root in ("objects", "applications")
        for path in (data_dir / root).rglob(".*.tmp")
    )
    return {
        "ok": not missing and not corrupt,
        "objects_checked": len(snapshots),
        "manifests_checked": len(applications),
        "missing": sorted(missing),
        "corrupt": sorted(corrupt),
        "orphan_objects": orphan_objects,
        "orphan_dossiers": orphan_dossiers,
        "temporary_files": temporary_files,
    }
