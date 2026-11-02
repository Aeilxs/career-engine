# End-to-End Milestone Runbooks (J0–J7)

**These are executable acceptance contracts, not claims that the product is implemented.** Each run starts from controlled input, passes through the actual application services and local SQLite, and finishes in a UI-observable state and durable artifact. Any current CLI command under J1–J7 is a **target interface**, not an implemented command.

## Shared runner contract

- Environment: locally built one-service Compose app, `./data` bind mounted, localhost-only HTTP. Test runs use isolated throwaway directories or Compose project configuration, never the operator's real application data.
- An E2E report must include: git SHA, image/config versions, UTC timestamp, fixture, commands, exit codes, expected vs actual rows, hashes, screenshots where needed, and explicit NOT TESTED items.
- Default acceptance has no real ATS/paid API access. Live discovery and J7 submission use separately enabled credentials and human approval.
- Test fault recovery by killing the actual process/container at relevant boundaries, not by only raising exceptions in a mocked service.

### J0 — `boot-and-restart` (implemented probe, not yet Mac-verified)

Input: empty local `./data`. Run `bash scripts/verify-j0.sh`. Docker builds, serves the J0 page and HTTP `/healthz`, writes a fresh marker to SQLite, stops/recreates the container, reads exactly the same marker. Pass only if the real HTTP response and DB marker match after restart; ensure data directory survives. Expected failures: missing lockfile, image build failure, permissions or broken binding are **failures**, not ignored results.

### J1 — `manual-ingest-to-xlsx` (NOT IMPLEMENTED)

Input: a synthetic text posting with source metadata. Import through UI, inspect normalized fields and source bytes; create a separate application; review tracker and export XLSX. Import same source ten times → one offer, one revision; edit content → R2; same title but different source ID remains separate. Kill/restart app then confirm records, revision history and XLSX↔SQL consistency. Missing file must error nonzero; malicious spreadsheet formula prefix must remain literal text. Acceptance: T01–T04/T14–T16/T21, plus real browser UI test.

### J2 — `source-scan-to-digest` (NOT IMPLEMENTED)

Prerequisite: P1 30-posting coverage audit. Input: configured public job board or a local stub exposing representative provider responses. First scan yields N offers; identical second scan yields zero; changed content yields one new revision. Inject 429, timeout, corrupted JSON and job closure; show status/digest without erasing previously captured offers. Restart mid-scan and verify recovery. A limited live read-only smoke test is optional, explicit and separate from offline CI. Acceptance: T20 and source-specific T01/T03.

### J3 — `offer-to-shortlist` (NOT IMPLEMENTED)

Input: approved synthetic professional profile and annotated offers. Evaluate hard requirements and preferences separately; render ordered offers with explanations and evidence. Missing salary or unmentioned requirement is UNKNOWN, not FAIL. Record model/prompt/validator/usage/cost; replay stored results without new provider calls; stop once budget exhausted. Human annotation dataset gives actual precision/recall and extraction errors. Acceptance: T05/T17/T18 and P2 report.

### J4 — `shortlist-to-approved-package` (NOT IMPLEMENTED)

Input: selected offer, approved synthetic facts. Build editable source and PDF, trace every relevant claim to fact IDs. Human reviews in UI, requests change, approves revision R1 by manifest hash. Edit source/answer → new R2; attempting to submit with R1 approval must fail. Display diff, required questions, artifact hashes and reviewer. PDF must pass extraction + visual inspection; unsupported claim must block. Acceptance: T06/T07/T09, P3.

### J5 — `approved-package-to-filled-form` (NOT IMPLEMENTED)

Input: local mock ATS with required fields, conditional questions, file uploads, validation and session expiration. Inspect, compare form semantic fingerprint, fill with approved revision and read back values/uploads. New required unknown field → block/review. Expired session → typed suspension. **No submit request.** Acceptance: T08/T10/T11/T19 and P4.

### J6 — `submit-and-reconcile` (NOT IMPLEMENTED)

Input: same local mock ATS, approved matching revision and form. Persist attempt state before POST. Simulator accepts one submission but drops acknowledgment. Restart. State remains `SUBMISSION_UNKNOWN`; reprocessing generates **zero extra POSTs**. Reconciliation with connector-specific proof can set SUBMITTED. A generic 200 or navigation success is insufficient. Acceptance: T12/T13/T16 and P5, remotely observed count exactly 1.

### J7 — `one-real-application-pilot` (NOT IMPLEMENTED)

Input: one personally chosen, genuinely interesting live opportunity on an ATS verified in J5/P6. Human explicitly approves the specific target, package revision and action. Inspect/fill, human verifies, submit once, capture proof/UNKNOWN and report elapsed time, manual corrections, browser errors and LLM cost. Never extrapolate one success to all ATS. Default CI does not run this. Acceptance: P6 report with explicit human sign-off.

## Regression contract

At each Jx run, rerun the accepted previous J0–J(x−1) offline E2E suite. A new feature must not make an earlier milestone's UI flow fail. Do not alter historical fixtures merely to suppress a regression; version a new fixture with rationale.

### J2 additional acceptance — `source-metadata-contract` (ADR-015)

This is a **separate, offline J2 run**, required in addition to `source-scan-to-digest` once TASK-J2-002 is implemented. From an isolated J1 v2 SQLite database, ingest a fixture with explicit remote/car/travel values, one with these values absent, and one with irrelevant extra company facts. Show the fixed nullable projection and direct access to the exact full source. Supply a URL-only string to manual text import and prove that no source/object/offer/revision rows were inserted. Attempt unsupported JSON keys and forged quotes and verify validation failures. Re-extract with same vs new extractor version and compare persisted historical results after process restart. Assert that source identity/provenance is not lost if different providers share byte-identical descriptions. J3 adds a spy test proving the full posting (not a prior model summary) is passed to the analysis boundary.
