# TASK-J3-001 — Approved Facts → Explainable Shortlist

**State:** TODO. **Prerequisites:** J2 accepted; maintainer-approved model/provider dependency and spending caps. **REQ:** 006, 019, 020. **Tests:** T02, T05, T17, T18.

## Scope

Implement structured approved profile facts, hard vs preferred job criteria, pass/fail/unknown per criterion, evidence-backed explanations and ranked shortlist. Introduce a narrow LLM client port with model/prompt/version/usage validation and cached replay. Keep deterministic fallback for tests; no external LLM calls by default.

## E2E

Given the frozen annotated synthetic corpus, render shortlist in UI, preserve missing salary as UNKNOWN, show citations, replay run without charges, change prompt version to create distinct record, and hit an artificial daily budget with zero further calls. Report actual accuracy and sample size when P2 is run live.

Do not invent skills, salary, employment probability or universal model quality guarantees.
