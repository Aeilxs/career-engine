# TASK-J6-001 — Mock Submission, Lost ACK and Reconciliation

**State:** TODO. **Prerequisites:** J5 accepted. **REQ:** 013–015, 017–018. **Tests:** T11–T13, T15–T16.

## Scope

Use mock ATS only. Persist a `SubmissionAttempt` BEFORE POST; verify exact approved revision and semantic form before sending. Require connector-specific proof for SUBMITTED. A confirmed server-side acceptance followed by dropped response must become SUBMISSION_UNKNOWN, not a success or retryable error.

## E2E

1. Server counts accepted submissions and can drop reply after recording one.
2. User authorizes one mock submission; DB records the attempt and remote server counts 1.
3. Kill the client after/during lost ACK, restart the application and worker.
4. Verify exactly 1 total remote creation, attempt remains UNKNOWN, no generic retry.
5. Reconcile from durable provider-specific evidence to SUBMITTED or remain UNKNOWN.

Review all failure modes, not only a happy POST 200 path.
