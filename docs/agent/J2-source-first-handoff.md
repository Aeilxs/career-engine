# GitHub Copilot Cloud Agent — J2 Source-First Handoff

Use `tasks/TASK-J2-002.md` as the authoritative feature ticket. Assign only after the maintainer has accepted J1, merged its fixes and pushed ADR-015 to the selected base branch.

## Copyable agent prompt

> Read `AGENTS.md`, `docs/decisions/ADR-015-source-first-limited-metadata.md`, `tasks/TASK-J2-002.md`, `docs/spec/contracts.md` and `docs/quality/test-matrix.md`. Implement **TASK-J2-002 only**. Preserve the existing J1 SQLite schema/history and source snapshots. Do not add dependencies or modify Docker/Compose/CI. Implement typed optional metadata with verifiable source evidence, reject URL-only manual text imports without persisting any garbage, and add offline regression tests. Run the specified checks and report exact outcomes. Do not fabricate extraction quality evidence or claim the task accepted. Open a PR for human review.

## First stabilize J1

For immediate work while PR #1 is open, assign the separate `tasks/TASK-J1-002.md` on base `feat/j1-manual-ingest-to-xlsx`. Do **not** mix it with J2. Merge J1, then apply/merge ADR-015 and assign J2 metadata as its own issue.

## Scope separation

- `TASK-J2-001.md` is the source discovery connector/digest job and remains a separate PR.
- Paid LLM extraction and scoring are J3 concerns requiring approved provider, budget, logging and test fixtures.
- Do not ask a cloud agent to fix J1 bugs and build J2 simultaneously; keep PRs separable.

## GitHub workflow

1. Create a GitHub Issue with the contents of `TASK-J2-002.md`.
2. Assign the issue to **Copilot** and select a branch that already contains accepted J1 plus ADR-015.
3. Review the generated PR, CI outcomes and actual regression evidence; accept or request corrections yourself.
