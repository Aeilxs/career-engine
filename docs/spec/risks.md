# Risks, Security and Operating Rules

These are **qualitative design estimates** (L/M/H), not measured incident rates. The human maintainer owns acceptance of residual risk; the assigned agent provides reproducible mitigation evidence.

| ID | Risk | Likelihood / Impact | Prevention / validation |
|---|---|---|---|
| R01 | Low ATS coverage among real target jobs | H/H | P1 sample of 30, prioritize measured sources; keep manual import |
| R02 | Forms change between inspection and submission | H/H | Semantic form hash and approval recheck; T08/T11 |
| R03 | Duplicate submission after timeout | M/H | Persist intent, UNKNOWN and reconcile, no generic retry; T13 |
| R04 | Old worker continues after lease expiry | M/H | One worker, lease generation, explicit shutdown; never reclaim submit; T16 |
| R05 | Invented expertise in CV | M/H | Source facts and claim checks, human review; T06 |
| R06 | False cross-site deduplication | M/M | Native identities, fuzzy proposals only; T03 |
| R07 | Sensitive information leaked in logs/files | M/H | Synthetic fixtures, secrets exclusion, minimal traces; T21 |
| R08 | HTML/URL/LaTeX injection, SSRF | M/H | Sanitization, redirects/IP/DNS checks, isolated rendering; T21 |
| R09 | SQLite on unsuitable filesystem / multiple hosts | M/H | Local bind mount, one worker, WAL, bounded contention; T24 if deployed |
| R10 | SQLite references missing files | M/H | Immutable object write-before-reference, hashes, reconciliation; T04 |
| R11 | Python 3.14/ARM image dependency failure | M/M | P0 lock/install/build qualification, no fake success |
| R12 | Unbounded paid LLM usage | M/M | Per-run/day quotas, max tokens, deadlines, bounded repair; T18 |
| R13 | Existing CV renderer incompatible | M/M | P3 five-case qualification / pluggable renderer |
| R14 | Artificial green CI from weakened tests | M/H | Test-diff review, CI negative control, T23 |
| R15 | Premature overengineering | H/M | One container and vertical milestone demos |
| R16 | Challenge/auth/session expiration | M/M | BLOCKED/NEEDS_HUMAN; no repeated unattended workaround; T19 |
| R17 | Disk loss with no backup | M/H | **Explicitly accepted** for local prototype; persisted container volume is not backup |

## External input handling

- Network calls are **disabled in default tests**. Live POCs must be gated and rate limited with explicit source configuration.
- For URL ingestion allow HTTP(S), validate DNS and resolved destination IP at every redirect, reject private/loopback/link-local and metadata endpoints except the explicit localhost ATS simulator test profile. Enforce request timeouts, body-size limits, bounded redirects, user-agent and Retry-After.
- Offer text, retrieved documents and form labels are data, **never prompts that override tool permissions**. No business LLM shell tool. Do not execute or render remote HTML in a privileged UI without sanitization. Escape HTML and LaTeX; render generated documents with shell escape disabled, resource/time limits, no network and a nonprivileged process.
- Uploaded names are not filesystem paths. Store with generated IDs/hashes under private directories. Validate paths, file types and maximum sizes. Treat resume files as sensitive.
- Secrets via ignored environment files; never commit credentials or browser cookies. Restrict session storage permission/duration. UI remains localhost-only unless a new auth/session/CSRF ADR is accepted.

## Retry and terminal behavior

| Outcome | Action |
|---|---|
| Read-only HTTP timeout or 429 | Max 3 bounded attempts with jitter, Retry-After and total deadline |
| Invalid LLM JSON | At most 1 repair if budget permits, then BLOCKED/FAILED |
| 401/403/session expired | Suspend and request human action; do not loop |
| Confirmed closed job / 404 | Preserve history, mark source unavailable |
| Newly required question | Return to human review with exact delta |
| Submission result ambiguous | `SUBMISSION_UNKNOWN`, no automatic retry |
| Artifact missing or hash mismatch | BLOCK until inspected/recreated as *new* revision |

## Operations

Structured log metadata: timestamp, level, job_id, application_id, run_id, stage, duration_ms, error_code — **not** full CV text or credentials. `doctor` checks local write access, schema compatibility and health without contacting real ATS or sending any test applications. One process failure must not turn an unconfirmed send into a confirmed send. Debug traces must be opt-in, bounded and protected.

No external backup job will be added by default. Optional manual SQLite backup may be designed later, but it must make DB/artifact consistency explicit and must not be represented as an accepted RPO/RTO target. Review `REQ-024` if persistence grows beyond disposable prototype data.
