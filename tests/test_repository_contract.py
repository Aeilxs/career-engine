"""Protect the stable requirement IDs and active milestone documentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_requirements_retain_all_original_ids() -> None:
    spec = (ROOT / "docs/spec/requirements.md").read_text(encoding="utf-8")
    for number in range(1, 28):
        assert f"REQ-{number:03d}" in spec


def test_validation_references_remain_traceable() -> None:
    matrix = (ROOT / "docs/quality/test-matrix.md").read_text(encoding="utf-8")
    for number in range(1, 26):
        assert f"T{number:02d}" in matrix


def test_all_milestones_have_task_and_e2e_runbook() -> None:
    runbook = (ROOT / "docs/quality/e2e-runs.md").read_text(encoding="utf-8")
    for number in range(8):
        assert (ROOT / f"tasks/TASK-J{number}-001.md").exists() or number == 0
        assert f"J{number} —" in runbook
