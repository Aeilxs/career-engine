# TASK-J5-001 — Mock ATS Inspection and Verified Fill (No Submit)

**State:** TODO. **Prerequisites:** J4 accepted, P4 browser capabilities qualified. **REQ:** 009, 012, 021. **Tests:** T08, T10, T11, T19.

## Scope

Build a local fake ATS with mandatory/conditional fields, select options, file uploads, validations and expired session outcomes. Implement a narrow Playwright-backed inspect/fill connector. Compare form semantic fingerprint with approved answers, capture unknown-required issues and verify readback on the mock server.

## E2E

Inspect → approved values → fill and validate uploads, no submit request. Add conditional required question and show BLOCKED/review. Change option and re-inspect; session expiration suspends. Recorded server-side fill data must match approved package. A re-render of an unrelated anti-CSRF token alone should not invalidate form semantics.

No live submits, no attempts to bypass challenges.
