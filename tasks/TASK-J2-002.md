# TASK-J2-002 — Source-First Canonical Metadata and URL-Only Guard

**State:** TODO — assigned only after J1 is accepted and ADR-015 is on the target base branch.
**Prerequisites:** stable J1 schema/migrations and source snapshots.
**Requirements:** REQ-001, REQ-002, REQ-003, REQ-023, ADR-015.
**Tests:** T01, T02, T03, T21, **T26–T29**.

## Objective

Make J1/J2 imports distinguish a valid posting document from an unresolved URL, and define one small, typed, evidence-backed metadata projection for known fields. Preserve the complete source and prepare for later LLM extraction **without calling an LLM**.

## Required behavior

1. Read the current J1 implementation first. Reuse its `SourceSnapshot`/`OfferRevision` model and actual persisted source bytes; do not replace existing schema, identity, hashes, manifests or UI flows.
2. Reject an input containing only an `http://` or `https://` URL when submitted to the manual **text** importer, both through CLI and API/UI. Return a specific validation message directing the user to URL discovery (TASK-J2-001); do not insert `unknown` offers, revisions, applications or snapshots. A valid job description containing a URL is still accepted.
3. Add a validated canonical projection with the existing core fields and **only** the six ADR-015 optional fields. Distinguish missing `null` from supported `false`/`0`. Validate enum/range constraints. Reject unexpected keys from proposed extractor outputs (no `metadata: dict[str, Any]` escape hatch).
4. Ensure every non-null extracted optional value has checkable source evidence (snapshot ID/hash and quote or source path/offset), extractor method/version and source revision identity. Detect nonexistent quotes, inconsistent units and unsupported assertions before persisting the projection.
5. Implement an offline deterministic extractor/fixture strategy to demonstrate the contract. Do not build a generic LLM orchestration layer, introduce a provider, change the image, install an XLSX library or migrate to NoSQL.
6. Persist metadata linked to a specific offer revision, without rewriting the raw source or older extraction records. A rerun under a changed extractor version creates a distinct record; an identical rerun is idempotent. If a schema migration is necessary, cover fresh DB, J1 v2 upgrade, concurrent initialization and restart.
7. The UI must show the six optional fields as explicit values or 'Not specified', while offering direct access to the original full posting. Do not display invented defaults.
8. Existing J0/J1 API, CLI, tracking, spreadsheet export and browser E2E remain unchanged in behavior. No source fetch, paid API or live job board call in default tests.

## Offline acceptance scenarios

- **URL-only input:** paste `https://example.org/jobs/123` in Posting Text; CLI and HTTP API refuse it, show a URL-specific error, and leave SQL + local objects unchanged. URL embedded in a substantive posting is accepted.
- **Tri-state and no inference:** `company_car` absent → `null`; explicitly 'no company car' → `false`; explicitly provided → `true`; remote location only does not imply remote policy; `remote_days_per_week=0` is not treated as missing.
- **Unsupported content:** give a fixture with average employee age 32 and no travel information. The age remains in the original posting, not in new metadata; `travel_required` and `travel_percentage` remain `null`.
- **Evidence:** fabricate a quote or source hash; validation fails before persistence. Import equivalent content twice under different source identities; both acquisition provenance records remain distinct even if stored bytes are deduplicated.
- **Versioning:** re-extract same source and extractor version → one logical extraction; new extractor version → new immutable extraction, preserving historical metadata; restart preserves it.
- **Regression:** all existing `pytest`, Ruff, mypy, Compose/runtime checks and J1 offline browser tests still pass. No modifications to their expected outcomes to make failures disappear.

## Delivery evidence

Report migration and data-model decisions, precise tests/commands/exits, a short UI demo, before/after row counts in isolated SQLite, and any intentionally unsupported field. Update `STATUS.md` only to 'implemented, awaiting acceptance'. The maintainer accepts the milestone.

## Explicitly forbidden scope

No arbitrary-key attribute registry, no LLM call, no copy/pasting derived summaries into the authoritative source, no automatic source crawling, no ATS submission, no changes to maintainer-owned Docker/Compose/CI/lockfiles without explicit approval. Do not implement TASK-J2-001 in this task unless assigned separately.
