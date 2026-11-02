# TASK-J1-002 — Stabilize SQLite Startup and Multi-Source Provenance

**State:** TODO — stabilization task for PR #1.
**Prerequisites:** J1 implementation branch (`feat/j1-manual-ingest-to-xlsx`), no J2 changes.
**Related contracts:** REQ-001, REQ-003, REQ-023; T01, T03, T21.

## Independent audit findings to reproduce

1. Concurrent DB initialization can intermittently produce `sqlite3.OperationalError: database is locked` (previous reviewer observed 3 failures across 35 stress series of six initializers under Python 3.13). **Reproduce under target Python 3.14 before claiming the fix**, and make the initialization path robust under contention without swallowing unrelated errors or weakening SQLite safety.
2. Byte-identical sources collected with different provider/source references can share a stored object but lose distinct acquisition provenance if the deduplication key is only content SHA-256. Keep content-addressed file deduplication but persist independent source/retrieval identity and time; don't accidentally merge two distinct offers.

## Acceptance

- Add a deterministic concurrency stress test with a barrier and separate connections/processes where appropriate. Include a bounded workload (at least 6 competing initializers, repeated at least 20 times) on Python 3.14. No lock errors, no partial schema, one correct migration state; preserve the J0 marker and J1 v1->v2 upgrade behavior.
- Demonstrate two different provider/source identifiers with identical content bytes. Exactly one backing object is acceptable, but **two attributable acquisition events** remain queryable, each tied to its source and offer/revision; no accidental Offer merge.
- Verify no changes to existing application-stage history, immutability triggers, XLSX values or J1 UI behavior. All 115 existing tests and offline J1 process/Docker E2E must still pass (test counts can legitimately increase).
- Record exact commands, target runtime, repetitions, errors and before/after DB counts in a report. No fabricated green result if unavailable.

## Scope restrictions

Do **not** implement J2, change the frontend framework, introduce dependencies or change Docker/Compose/CI without explicit approval. Do not change test expectations just to bypass the defect. Report findings and propose narrow schema migration if required. Leave final PR acceptance to maintainer.
