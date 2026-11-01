# TASK-P1-001 — Audit Coverage of 30 Relevant Real Job Postings

**State:** TODO. **Owner:** human-guided research/agent. **Parallel:** J0/J1. **Must precede connector choice in J2.**

## Task

Collect 30 genuinely relevant postings (prefer many employers) in the target roles and geography. Record the ATS provider or board, access URL, observed read route, publication date if known, region, source freshness and notes on candidate-side submission constraints. Distinguish unknown capability from unavailable capability. Do not collect login cookies or candidate private data.

## Acceptance

- Exactly 30 rows with date-checked source references and a clear provenance trail.
- Counts by provider and percent covered by each possible read connector (denominator stated).
- Recommendation of first read connector based on *real relevance and coverage*, not easiest API.
- No claim that any public read API permits automated candidate submission.
- Produce `reports/P1-<date>.md` with tabular anonymized observations and blockers.

No default CI network access and no unrelated implementation work.
