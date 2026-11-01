# TASK-J1-001 — Manual Posting → Application Tracker → XLSX

**State:** IMPLEMENTED BY AGENT, NOT ACCEPTED (see `reports/J1-2026-11-01.md` for evidence and deviations; React/Vite/TypeScript and a third-party XLSX library were not introduced because they need a separate maintainer-reviewed prerequisite). **Prerequisites:** P0/J0 accepted; maintainer reviews React/Vite/TypeScript and XLSX dependencies/lock/build changes as a separate prerequisite. **REQ:** 001–005, 016–018, 023, 025. **Tests:** T01–T04, T14–T16, T21.

## Scope

Implement the actual Web UI for manual text/file import, immutable source snapshot + normalized offer, distinct application creation, tracker view and downloadable XLSX projection. CLI calls the same use-case services. Keep exact native source identities and nullable unknowns; no LLM, live ATS, Playwright or submission.

## Deterministic E2E

1. Start app with isolated local DB and import a synthetic offer via browser.
2. Verify source provenance, normalized fields, offer/application separate records.
3. Reimport 10 times: one Offer/Revision. Change source text: R2. Similar title from distinct source: separate Offer and a non-destructive fuzzy-duplicate suggestion (no automatic merge).
4. Create one application, update status with transactional event, export XLSX and read back rows to compare with SQL.
5. Restart container, verify records and artifact hashes; reject missing file without half-written data.
6. Inject XLSX formula-like title (`=1+1`) and verify it is stored/exported as inert text.

## Delivery

UI screenshot, exact commands/exits, DB row count and object hashes, real restart proof. Never mark complete based only on Python service tests.
