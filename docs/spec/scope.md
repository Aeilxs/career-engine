# Product Scope and User Journey

## Primary user and purpose

One candidate uses Career Engine on their own Mac to discover and prepare relevant job applications, keep a clear global tracker and selectively automate a form with explicit human approval. The profile may contain French or English professional facts; the **developer documentation and initial UI are in English**. UI localization is a later product choice.

## Target workflow

1. Collect a posting manually or from a configured read-only ATS board.
2. Preserve the exact source and provenance; normalize fields and deduplicate without merging distinct jobs.
3. Evaluate approved candidate criteria and highlight evidence, gaps and unknowns.
4. Create an application *only after human selection*, independently from the job offer.
5. Choose approved professional facts, prepare editable documents and inspect form requirements.
6. Edit/review/reject/approve a specific immutable package revision.
7. On a qualified ATS only: inspect current form, fill/read back, obtain explicit send authorization, submit once, reconcile evidence or uncertainty.
8. Track recruiter status separately and export a global XLSX view.

## Boundaries and explicit non-goals

- No universal jobs search, general-purpose web agent, mass application submission, recruiter email conversation automation, negotiation engine or multi-user SaaS.
- No cloud deployment prerequisite. No automatic R2 backups, k3s, PostgreSQL, Garage, Redis, brokers or vector search in the MVP.
- Authentication challenges, session expiry and unknown required fields should be represented as **human-action-needed** states. The first milestones must not depend on bypassing challenges.
- No unreviewed use of a personal resume/CV generator. Its existing implementation is a **candidate integration**; qualify with P3 first.

## Capacity assumptions, not measured guarantees

One active candidate, one local worker and one active browser; design test envelope around 100 imports/day and 10,000 stored offers. Raw documents and traces may dominate storage. Proposed initial targets for local list views (p95 under 500 ms excluding network) and restart recovery are goals to measure, not accepted performance results. Since backup is deliberately deferred, there is no promised RPO or RTO following disk loss.

## Human contribution

Keep modules small enough for manual reading in Neovim, PRs focused and acceptance visible through UI. Dashboard must make missing information, changes and blocked actions apparent. A model-produced score does not predict hiring probability. Editing a PDF externally creates a new imported artifact/revision; no approved document is overwritten silently.

## Deliberately limited structured representation (ADR-015)

The structured offer record is a concise **filtering and tracking view**, not an exhaustive knowledge graph. Beyond existing canonical fields, the only approved optional projections are remote policy, remote days/week, company car, travel required, travel percentage and minimum experience years. All other claims (for example average employee age or novel benefits) remain in the source posting unless a later human-approved requirement gives them a product use case. A later LLM stage reads the faithful full source, not a prior model's interpretation; absence of a field never implies a negative value.
