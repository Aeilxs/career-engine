# Product Roadmap — Vertical Milestones J0–J7

**The implementation remains a local-first, one-container monolith.** Each milestone must produce an observable UI result backed by real SQLite/files, exercise its own end-to-end run, and retain the behavior of earlier milestones. Completion requires human acceptance of evidence, not an agent status assertion.

| Gate | Delivered behavior | Assigned task | Required E2E run |
|---|---|---|---|
| P0/J0 | Verified Python 3.14, locked deps, one-container runtime, API + UI, SQLite survives container recreation | TASK-BOOT-001 | `boot-and-restart` |
| P1 | Classify 30 target postings by provider, inspect accessibility and coverage | TASK-P1-001 | `source-coverage-audit` |
| J1 | Manual offer import, immutable revisions, separate application, tracker UI, XLSX | TASK-J1-001 | `manual-ingest-to-xlsx` |
| J2 | Configured read-only source scan, incremental digest, errors and restart | TASK-J2-001 | `source-scan-to-digest` |
| J3 | Approved profile facts, explainable matching, measured LLM budgets | TASK-J3-001 | `offer-to-shortlist` |
| J4 | Editable CV + PDF, versioned package, human diff/review/approval | TASK-J4-001 | `shortlist-to-approved-package` |
| J5 | Mock ATS inspection/conditional fields/uploads and safe fill only | TASK-J5-001 | `approved-package-to-filled-form` |
| J6 | Mock ATS send intent, proof, lost ACK → UNKNOWN and reconciliation | TASK-J6-001 | `submit-and-reconcile` |
| J7 | One expressly authorized real application with reported proof/UNKNOWN | TASK-J7-001 | `one-real-application-pilot` |

## Work order

Run P1 sourcing research in parallel with J0/J1, but **do not** assign J2 before J1 has stable offer identity and revisions. A valid P1 report must be produced before choosing the J2 connector. Approve a separate dependency/build task before introducing the J1 React toolchain. Do not start J5/6/7 submission work before the human-review model and simulator have passed.

## Deliberate out of scope

Universal cross-ATS search, universal apply bot, bulk submissions, multi-user login, remote UI, k3s deployment, cloud backup, Redis, PostgreSQL, S3, message brokers, vector DB, self-running shell-enabled LLM agents, recruiter email automation. These need distinct business justification and ADRs, not a speculative agent task.

## Split tasks when necessary

A ticket too large for coherent review must be split with original acceptance criteria intact. For example J5 may become mock ATS server, inspector, form-filling and browser readback subtasks, but the milestone is complete only when the final E2E run is passed. Avoid simultaneous agents editing schema/lockfiles or the same contract.
