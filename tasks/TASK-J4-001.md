# TASK-J4-001 — Reviewed Package with Editable CV and PDF

**State:** TODO. **Prerequisites:** J3 accepted, P3 document renderer POC. **REQ:** 007, 008, 010, 011. **Tests:** T04, T06, T07, T09.

## Scope

Prepare an immutable package backed by approved profile facts, editable source documents, generated PDF, form answers where known, artifact hashes and human review/diff/approve/reject/request-changes operations. Existing LaTeX CV generator may be integrated only after P3 contract and sample PDFs pass.

## E2E

Select offer → generate package R1 → inspect source facts and PDF in UI → approve R1 → edit one fact/answer → new R2 and no approval of R2. Attempt to authorize R1 after revision change and verify explicit rejection. Test concurrency conflicts, unsupported assertions and PDF visual/readback checks.

No real form fill or submission.
