# Domain, Interface and Data Contracts

These are **proposed stable conceptual contracts**. Pydantic models, DB migrations and JSON Schemas become executable when implementing the relevant ticket. Do not maintain hand-edited JSON Schema copies that can diverge from code.

## Canonical entities

| Entity | Essential fields | Hard constraints |
|---|---|---|
| `SourceSnapshot` | id, source_ref, retrieved_at, mime, http_status/error_code, content_sha256, connector_version, object_ref | Immutable, content-addressed bytes; identical content can share storage |
| `SourceAcquisition` | id, snapshot_id, offer_revision_id, source_ref, source_id, provider, board, retrieved_at | Immutable record per retrieval; content deduplication never merges source identity or offers; `snapshot_id` must equal the revision's snapshot (DB trigger); `SourceSnapshot.source_ref`/`retrieved_at` describe only the first stored source, acquisitions are authoritative |
| `Offer` | id, provider, board, external_id, canonical_url, current_revision_id | Native source identity preferred; a content hash is not a universal offer ID |
| `OfferRevision` | id, offer_id, snapshot_id, title, company, locations, contract, salary, description, apply_url, provenance | Immutable; missing data is unknown; updated content creates a new revision |
| `Salary` | min, max, currency, period, compensation_kind, gross_net, raw_text | Decimal; min ≤ max; fixed/variable/total and gross/net not guessed |
| `ProfileFact` | id, kind, text, period, evidence_ref, verified_by, verified_at | Only approved facts justify final CV claims |
| `Analysis` | offer_revision_id, criterion_results, gaps, evidence_refs, model_run_id | Per-criterion pass/fail/unknown; score not an employment probability |
| `Application` | id, offer_id, candidate_profile_id, stage, recruiter_status | Separate lifecycle from offer and from submission attempt |
| `FormSnapshot` | id, destination, inspected_at, fields, semantic_sha256, coverage | Coverage complete/partial/unknown; unobserved fields are not proof of absence |
| `FormField` | connector_key, label, type, required, options, condition, constraints | Unknown required field or option blocks submission |
| `Answer` | field_key, value, origin, referenced_fact_ids, reviewed | Origin profile/human/generated; declared personal facts require human approval |
| `PackageRevision` | id, application_id, parent_revision_id, source_hashes, artifacts, answers, manifest_sha256 | Immutable; referenced files and hashes verified |
| `Approval` | package_revision_id, manifest_sha256, reviewer, created_at, approved_target | Specific and revocable-by-new-revision; no blanket future approval |
| `SubmissionAttempt` | id, application_id, revision_id, connector_version, state, created_at, proof_refs | Persisted before external effect; never deleted to facilitate retry |
| `Job` | id, kind, input_hash, status, generation, lease_expires_at, result_refs, error_code | Durable processing; at most one claim for a logical attempt |

All persisted timestamps: UTC ISO-8601 with explicit offset; display timezone may differ. Internal IDs are UUIDs; external IDs are opaque strings. External JSON has a `schema_version` and explicit provenance references.

## Provenance and deduplication

For each extracted field store source snapshot plus JSON path or exact substring/offsets (where applicable). Citation presence establishes origin, not interpretation correctness. Generated CV sentence → approved `fact_ids` → immutable profile revision. Validate numbers, dates, seniority and stated responsibility explicitly.

Prefer provider-native exact identity `(provider, region, board_id, external_id)` where available. Connector-specific canonical URL processing must preserve parameters that identify a posting. Across providers, offer equality is *suggested*, never assumed. Similar titles and employers do not imply the same vacancy.

## Application state outline

```text
DRAFT → PREPARING → REVIEW_REQUIRED → APPROVED
                     ↘ BLOCKED
APPROVED → SUBMITTING → SUBMITTED
                       ↘ SUBMISSION_UNKNOWN
                       ↘ REJECTED_CERTAIN
SUBMISSION_UNKNOWN → (human or connector reconciliation) → SUBMITTED / NOT_SUBMITTED_CERTAIN / UNKNOWN
```

The recruiter's status (`applied`, `interview`, `rejected`, etc.) is separate from the technical state. Treat `SUBMISSION_UNKNOWN` as terminal for automatic retries; only explicit reconciliation and fresh human authorization may allow another attempt.

## Connector boundaries

- `OfferSource.fetch(ref) -> SourceSnapshot`; `normalize(snapshot) -> OfferRevision`.
- `LLMClient.run(task, input, output_schema, budget) -> ValidatedRun | typed_error`.
- `DocumentRenderer.render(input, template_version) -> ArtifactSet`.
- `ApplicationConnector.inspect(target, session) -> FormSnapshot`.
- `.fill(revision, form) -> FillReport` including values read back and unknowns.
- `.submit(persisted_attempt, revision) -> Confirmed | RejectedCertain | Unknown`.
- `.reconcile(attempt) -> Confirmed | NotSubmittedCertain | Unknown`.

Connector capability flags distinguish `read`, `inspect`, `fill`, `submit`, `reconcile`. A public read endpoint never implies candidate-side submission access. **LLM tools are not allowed to call `submit`.**

## CLI target (not implemented until the referenced milestone)

```bash
career ingest --file offer.txt
career offers list
career application create --offer <OFFER_ID>
career application prepare <APPLICATION_ID>
career application review <APPLICATION_ID>
career application approve <APPLICATION_ID> --revision <REV> --hash <HASH>
career application submit <APPLICATION_ID> --revision <REV>
career application reconcile <APPLICATION_ID>
career export --format xlsx --output applications.xlsx
career worker
career doctor
```

Suggested exit codes: 0 locally successful/enqueued with explicit `job_id`, 1 internal failure, 2 bad args, 3 conflict, 4 blocked, 5 uncertain external outcome. Enqueued is **not** submitted. Machine output `--json` should include status/entity_id/job_id/error_code.

HTTP API candidates: `POST /imports`, `POST /applications`, `POST /applications/{id}/revisions`, `POST /applications/{id}/approvals`, `POST /applications/{id}/submissions`, `GET /jobs/{id}`. Sensitive mutations need expected-version checks. HTTP 202 means accepted/queued; 409 means conflict. GET never triggers an external side effect.

## XLSX contract

Stable columns: application_id, offer_id, company, position, location, URL, imported_at, technical_stage, recruiter_status, revision, approved_at, confirmed_submitted_at, last_error, next_action, dossier_path. A metadata tab records schema_version, exported_at and filters. Export from a coherent SQL snapshot, write to a temporary file, then atomically replace. Encode any external user text as text: `=`, `+`, `-`, `@`, control prefixes must not evaluate as formulas.

## Human review contract

Edits produce new revisions with parent and diff. Edits to facts belong to the profile, not merely a generated PDF. Review UI displays target, source facts, changed fields, generated artifacts, answers, unknown required questions and precise approval hash. Conditional questions discovered later return the package to review.

## Source-first typed metadata projection (ADR-015; J2/J3)

The canonical full job posting remains the immutable source (original bytes plus faithful, versioned full-text rendering when necessary). A projected metadata document is **not** a replacement for the posting and must never become the sole prompt input for a downstream analysis LLM.

Fixed optional attributes (no arbitrary keys): `remote_policy` (`onsite`, `hybrid`, `remote` or null), `remote_days_per_week` (integer 0–7 or null), `company_car` (boolean or null), `travel_required` (boolean or null), `travel_percentage` (number 0–100 or null), `minimum_experience_years` (non-negative number or null). Existing offer core fields remain as they are and retain their provenance. These six optional fields are candidate-facing conveniences, not a full semantic representation of the job posting.

Each non-null optional field must have verifiable evidence from an immutable snapshot, including the exact referenced source identity and an excerpt/path/offset where feasible. `false` and `0` require explicit support; missing, ambiguous and contradictory inputs remain `null`. An extraction run records its source revision, method/version, validator and results; changed extractor version does not overwrite historical records. See `tasks/TASK-J2-002.md` for executable acceptance and migration requirements. The future J3 LLM adapter must use the same fixed, validated output contract; its analysis prompts read the full posting directly.
