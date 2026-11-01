"""Conventional Commit validator works without external tools."""

import importlib.util
from pathlib import Path


def test_commit_subjects() -> None:
    path = Path(__file__).resolve().parents[1] / "scripts" / "check-commit-msg.py"
    spec = importlib.util.spec_from_file_location("commit_conventions", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.valid("feat(offers): import source snapshots")
    assert module.valid("chore: bootstrap career engine")
    assert module.valid("fix!: remove obsolete API contract")
    assert not module.valid("added feature")
    assert not module.valid("feat: ")
    assert not module.valid("Feat: camel case type")
