# TASK-J2-001 — One Read-Only Source → Incremental Digest

**State:** TODO. **Prerequisites:** J1 accepted, P1 coverage report. **REQ:** 001 (URL completion), 002–004, 018 (durable scan jobs), 022, 023. **Tests:** T01, T03, T20, T21.

## Scope

Select one relevant ATS/job board backed by P1, implement a **read-only** source adapter with configured board/identifier, raw snapshots, typed errors, incremental scanning and visible digest. Prefer official read endpoints when available; never assume read API implies candidate submission permission.

## E2E

Use local HTTP fixtures offline. First scan adds N, identical second scan adds 0, changed body creates R2, failing/429 endpoint preserves earlier entries and records typed failure. Restart mid-scan and continue without duplicate records or created Applications. UI and CLI invoke the same service. Live verification, if used, must be explicit, bounded and separate from CI.

## Delivery

Observed provider coverage, measured results, saved digests and precise failures. No generic crawler or auto-submit logic.
