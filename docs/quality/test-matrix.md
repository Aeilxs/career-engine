# Canonical T01–T25 Test Matrix

Reference IDs preserve the original v0.1 validation catalog. **These are tests to implement and execute, not tests already passed.** See [requirements](../spec/requirements.md).

| Test | Observable assertion | Milestone / level |
|---|---|---|
| T01 | File import and failed remote retrieval remain inspectable after restart | J1/J2, integration |
| T02 | Missing fields, currency/period and provenance match hand annotations | J1/J3, contract + evaluation |
| T03 | Ten same imports, URL variants, changed revision, distinct similar job | J1, integration |
| T04 | Package/object manifest hashes match; missing file detected | J1/J4, integration |
| T05 | Missing criterion stays UNKNOWN with evidence-based explanation | J3, unit + evaluation |
| T06 | Missing fact, false reference, exaggerated responsibility, changed date flagged | J4, unit + human review |
| T07 | Long CV, accents, text extraction, PDF visual inspection | J4, integration + manual |
| T08 | New conditional field, changed option, unknown required field block | J5, browser E2E |
| T09 | Approve R1/edit R2; R1 approval no longer authorizes; concurrent edit conflict | J4, integration |
| T10 | Mock ATS verifies readback of values and uploaded file contents | J5, browser E2E |
| T11 | Semantic form change invalidates approval; irrelevant CSRF token rotation does not | J5/J6, E2E |
| T12 | HTTP 200 without specific confirmation is never SUBMITTED | J6, E2E |
| T13 | Remote server accepts then loses response; restart does not create duplicate | J6, fault injection |
| T14 | XLSX readback matches SQL and external formula strings remain inert | J1, integration |
| T15 | Injected SQL error leaves neither partial transition nor orphan history event | J1, integration |
| T16 | Competing claims, expired lease and old active worker cannot double-process | J1+/J6, concurrency |
| T17 | Re-run uses persisted LLM result; prompt-version change creates distinct run | J3, integration |
| T18 | Timeout, invalid JSON, quota and spent budget give bounded retry/failure | J3, contract |
| T19 | Expired session, challenge and closed offer lead to typed suspension/recovery | J5, E2E |
| T20 | Two scans of same board create zero applications and no duplicate offers | J2, integration |
| T21 | Private URLs/redirect, HTML/script, traversal and secret sentinel blocked | J1+/J5, security |
| T22 | Coherent restore to a fresh directory, DB integrity + all hashes | **Deferred** under ADR-013 |
| T23 | Deliberately failing test makes command and CI fail nonzero | J0, CI control |
| T24 | Fresh deployment target, migration/worker RAM, latency and restart | **Deferred** k3s gate; Mac container smoke is J0 |
| T25 | Manual recruiter status update preserves immutable submission proof | J7+, integration |

## Test strategy

Test the real database and file system under `tmp_path`, avoid mocking the properties under examination. Use local HTTP and synthetic fixtures for connector tests. Recorded LLM outputs are deterministic replay inputs; they are not proof of live model quality. For PDF, verify both document content and human visual output; binary identical PDFs require an intentionally normalized build.

CI must not silently skip a failing test. The commit/PR evidence identifies which Txx was run and where the output can be reproduced.
