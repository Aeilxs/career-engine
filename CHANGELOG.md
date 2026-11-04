# Changelog

All notable changes will be recorded in this file. Commit messages follow Conventional Commits.

## Unreleased

### Added

- Local Python/FastAPI/SQLite bootstrap with a persistent Docker bind mount.
- English active requirements and domain contracts, end-to-end milestones J0–J7, traceability and risk catalog.
- Maintainer-owned runtime guardrails, agent contract, PR template, optional Conventional Commits hook.

- J1 (pending acceptance): manual posting import with immutable snapshots and revisions, fuzzy duplicate suggestions, separate applications with manifests, transactional stage history, stdlib XLSX export, integrity verification, durable job queue, dependency-free web UI, CLI parity, and unit/integration/API/restart/browser-E2E tests.

### Changed

- SQLite schema is now migrated v1 → v2 on startup (J1 domain tables; evidence tables are immutable via triggers).
- Reordered development to deliver real read-only source discovery at J2.
- Explicitly deferred offsite backup and Kubernetes deployment requirements during the local prototype.

### Not yet validated

- Python 3.14 lockfile resolution, Mac ARM64 Docker build, J0 container restart verification.
