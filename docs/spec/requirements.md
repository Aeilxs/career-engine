# Business Requirements and Traceability (Canonical English Specification)

**Source:** supplied v0.1 study, REQ-001–REQ-027. These stable IDs and acceptance intent are retained. **Scope modifications:** J2 discovery is brought forward under ADR-014; automated offsite backup and k3s deployment are explicitly deferred under ADR-013. A requirement is verified only by a test tied to a commit, execution command and observed evidence.

Legend: `M` mandatory for the stated milestone, `S` optional/deferred. `Txx` links to the canonical [test matrix](../quality/test-matrix.md). All status values are **NOT IMPLEMENTED** unless a dated report says otherwise.

| ID | Gate | Requirement and measurable acceptance | Test |
|---|---|---|---|
| REQ-001 | M/J1–J2 | Import text/file at J1 and secure URL at J2; preserve raw bytes, timestamp, source, content hash and retrieval outcome. Failed retrieval never invents an offer. Full REQ acceptance requires both paths. | T01 |
| REQ-002 | M/J1 | Normalize title, company, locations, contract, description and apply URL. Missing information is `null`/unknown with field-level provenance. | T02 |
| REQ-003 | M/J1 | Reimport the same ATS identity ten times: one offer; create a new immutable revision only when normalized/source content changes. | T03 |
| REQ-004 | M/J1 | Suggest fuzzy cross-source duplicates for human decision, never automatically merge distinct positions. Deterministic exact duplicate logic is required first; fuzzy suggestions may follow within J1 scope if tested. | T03 |
| REQ-005 | M/J1 | Each created `Application` has a separate inspectable folder/manifest from the ingested `Offer`; all stored objects are hash verifiable. | T04 |
| REQ-006 | M/J3 | Match hard requirements and preferences separately; `unknown` is not `failed` and scores have evidence-based explanations. | T05 |
| REQ-007 | M/J4 | Each CV assertion cites an approved professional fact; known contradictions block approval or are explicitly surfaced for review. | T06 |
| REQ-008 | M/J4 | Produce readable PDF and editable source without creating unsupported qualifications/experience. | T07 |
| REQ-009 | M/J5 | Inspect form fields, types, options, required conditions and unresolved questions; do not proceed when unknown required fields remain. | T08 |
| REQ-010 | M/J4 | Package revisions are immutable; approval binds to one manifest hash. Any change creates a new unapproved revision. | T09 |
| REQ-011 | M/J4 | Human edit, diff, reject and change-request flows exist; revision conflicts surface explicitly. | T09 |
| REQ-012 | M/J5 | Form filling is allowed only through an explicitly compatible connector; read back values and uploaded files before allowing submit. | T10 |
| REQ-013 | M/J6 | Immediately before submission, recheck current approved package, selected destination and semantic form fingerprint. | T11 |
| REQ-014 | M/J6 | Persist the attempt before invoking any external submit effect; mark confirmed only when connector-specific proof is stored. | T12 |
| REQ-015 | M/J6 | Crash/timeout around submit leaves an uncertain state; no generic worker restart may resubmit automatically. | T13 |
| REQ-016 | M/J1 | Reproducible XLSX export from SQL with stable IDs, typed dates, filters and no formula interpretation of external strings. | T14 |
| REQ-017 | M/J1 | Persist transitions, actor and reason atomically with each state change. | T15 |
| REQ-018 | M/J2+ | Durable jobs, bounded recovery and no concurrent double processing. The first long-running J2 scan requires the persistent job-claim loop. | T16 |
| REQ-019 | M/J3 | Persist LLM prompt version, model, parameters, input/output hashes, validator, usage and results for each execution. | T17 |
| REQ-020 | M/J3 | Bound per-run and daily LLM budgets; stop initiating new requests at limit; classify failures and cap retries. | T18 |
| REQ-021 | M/J5 | Classify authentication challenges, expired sessions and closed offers; suspend with recoverable context rather than infinite retry. | T19 |
| REQ-022 | M/**J2** | Incremental discovery against configured sources, dedupe and digest of new/changed offers. Does not promise universal job search. | T20 |
| REQ-023 | M/J1+ | No secrets in Git/logs; render external content inert; validate external URLs/redirects; minimize outbound access and injection exposure. | T21 |
| REQ-024 | **DEFERRED** | Original v0.1 required coherent DB+artifact backup/restore on a fresh environment. Not a J0–J7 acceptance gate by explicit local-only/no-offsite-backup decision. Keep its ID and residual disk-loss risk visible. | T22 (deferred) |
| REQ-025 | M/J0+ | Deterministic contract/integration tests run offline; CI must fail on a genuine failing assertion. | T23 |
| REQ-026 | **DEFERRED** | Original v0.1 required target-architecture deployment/benchmark and no implicit Mac dependency. k3s deployment is not required for the local-first prototype; Docker-on-Mac qualification remains J0. | T24 (deferred) |
| REQ-027 | S/J7+ | Record manual recruiter status and notes without changing technical submission evidence; automated emails are out of scope. | T25 |

## Domain invariants

1. Missing information is **not permission to invent a fact**.
2. No application is created merely because an offer was imported; offer and application identities are separate.
3. Approved content is immutable; submission must refer to the specific version, answers and compatible form fingerprint reviewed by the human.
4. Success requires durable evidence, not an intent, accepted task or optimistic HTTP status.
5. Unknown external submission outcomes **must not be retried automatically**.
6. SQL is the source of business truth; raw source and artifacts are evidence; XLSX and UI are projections.
7. Acceptance tests cannot be weakened to hide defects; every proof states the command, environment, commit and exact outcome.

## Planned tracing method

`REQ-ID → task → Txx → test module/fixture → commit SHA → reports/Jx-<date>.md`. Every new task must contain this map. A status in a ticket is never substituted for a run report.

## Reconciliation notes

- Old phases A/B/C/D are replaced by J0–J7; do not follow old task ordering blindly. Full URL ingestion in REQ-001 completes at J2 (manual file import at J1); durable background jobs in REQ-018 enter at J2 when long-running scans appear.
- The original proposed CLI-first + HTMX UI is superseded by a Web-first React/Vite frontend (introduced at J1), while the CLI remains an operational path to the **same** business services.
- An old RPO/RTO and 24-hour backup target is not applicable to the accepted no-backup experiment. Data durability across *container recreation* remains mandatory.
