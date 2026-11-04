# ADR-015 — Source-First, Limited Typed Offer Metadata

**Date:** 2026-11-02
**Status:** Accepted for J2/J3 design (implementation remains subject to acceptance tests).
**Supersedes:** Any proposed arbitrary-key attribute registry, dynamic ontology, or document-database migration for the bootstrap.

## Context

Job postings contain heterogeneous prose. Career Engine needs a small number of dependable fields for listing, filtering, tracking and choosing what to inspect, **not** a lossless structured re-encoding of every statement in an offer.

A chain `raw posting -> LLM summary/attributes -> downstream LLM analysis` risks compounding mistakes. J1 already persists immutable source snapshots, offer revisions and field provenance. SQLite and local files are the approved runtime; a NoSQL server or arbitrary metadata catalog has no demonstrated benefit.

## Decision

1. **Source of evidence:** preserve the exact received bytes, a stable source identity, retrieval time and SHA-256. For HTML/API inputs, also make a faithful *full-text* representation available to the LLM; it must be reproducible from the snapshot, associated with its hash and transformation version, and must not silently discard job-description content. Keep HTML/JSON payloads themselves when present. Do not claim a text representation is lossless if extraction loses content.
2. **Small fixed projection:** expose the existing canonical fields (title, employer, location(s), contract, salary, application URL, dates where available) and the explicitly approved optional fields only:
   - `remote_policy`: `onsite | hybrid | remote | null`
   - `remote_days_per_week`: integer in `[0, 7]` or `null`
   - `company_car`: `true | false | null`
   - `travel_required`: `true | false | null`
   - `travel_percentage`: number in `[0, 100]` or `null`
   - `minimum_experience_years`: non-negative number or `null`
   Avoid new keys without a reviewed contract change; leave other content in the full posting.
3. **Unknown is not false:** missing, ambiguous or contradictory facts stay `null` (and may carry a reason). `false` and `0` are used only when explicitly supported. Do not infer `onsite` merely from a city being listed or infer a company car from a job title.
4. **Evidence and repeatability:** each populated projected field must identify its immutable source snapshot plus a checkable excerpt/path/offset where applicable and extraction method/version. Deterministic and LLM extractors produce the same validated contract. No model-provided confidence score is accepted as proof of correctness.
5. **No cascade of interpretation:** ranking, CV generation and application preparation read the full posting representation and approved candidate facts. Extracted metadata may be used for list display, filtering and routing but never as the sole substantive context of a later LLM task. Stored previous LLM narratives are not primary evidence.
6. **State/versioning:** an extraction is tied to one offer revision and extractor version. Reprocessing must not overwrite source bytes or historical results. Record new extraction attempts/results separately, and make any 'current metadata' projection explicitly selected and reproducible.
7. **Explicit acquisition mode:** entering only a URL into the J1 manual *text* importer must be rejected with a helpful message and zero database mutations. In J2, URL acquisition uses a dedicated validated fetch path, bounded size/time, host/redirect checks and a typed failure if retrieval is impossible. Never persist a synthetic `unknown` posting for a failed fetch.
8. **No arbitrary JSON property bag, ontology, embeddings or NoSQL migration.** The full source is the extensibility mechanism. Add a new typed field only when a concrete UI/filtering need and tests justify it.

## Sequencing

J2 delivers source-aware acquisition and deterministic **typed metadata projection**, validation, provenance, error behavior and E2E. The J2 projection is useful without an LLM; do not introduce a paid provider or dependency changes in this task. J3 introduces a budgeted, schema-constrained LLM adapter (subject to maintainer approval) that uses the **same** projection fields and reads full source directly. J3's matching analysis must independently read the original posting, not merely the projected metadata.

## Alternatives considered

- **Arbitrary LLM-generated JSON / attribute registry:** expressive, but scope and synonym normalization would eclipse product value. Rejected for bootstrap.
- **Embedded document/NoSQL database:** does not improve source truth or eliminate transaction needs; incurs migration risk from the J1 SQLite schema. Rejected.
- **Fixed fields without original source:** insufficient to re-evaluate jobs or correct an extraction. Rejected.

## Consequences and migration constraints

The projection schema is intentionally incomplete. Users can still inspect any unusual details in the full posting. Avoid re-ingesting old sources merely to introduce optional fields; re-extract from existing snapshots where possible. Changes to SQLite require an idempotent migration, an upgrade path from J1 schema version 2 and preservation of all existing offers, revisions, applications, history, job leases and J0 markers.

No network/paid model calls in default CI. Existing J0/J1 E2E must remain green. A schema change must be justified with a migration and regression tests, not a replacement database.

## Acceptance evidence

See `tasks/TASK-J2-002.md` and tests `T26`–`T29` in `docs/quality/test-matrix.md`. A live LLM quality measurement is a **J3 evaluation**, not an assertion that JSON validity guarantees factual accuracy.
