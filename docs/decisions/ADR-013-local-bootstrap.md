# ADR-013 — Local-First Single-Container Runtime

**Date:** 2026-11-01  
**Status:** Accepted for the bootstrap by the human maintainer; any change requires explicit review.

## Context

Career Engine is a personal desktop-led application, primarily developed on an Apple Silicon Mac. The existing Raspberry Pi k3s cluster runs Garage S3 but has no PostgreSQL deployment. Installing new shared infrastructure does not improve early product validation. The operator explicitly prefers disposable containers and local persistent data, with no required offsite backup.

## Decision

- Modular Python 3.14 application using `uv`, FastAPI, and SQLite WAL; frontend React/Vite/TypeScript added at J1 once dependencies are reviewed.
- **One Docker image and one Compose service** with one Uvicorn worker and at most one durable job-claim loop in initial operation.
- Bind mount `./data:/data`; SQLite at `/data/career.db`; document content and evidence stored as local files under `/data`. No S3 or remote SQL dependencies.
- Host binds **only to `127.0.0.1:8000`**. No J0 authentication or remote access. Backend may use a local subprocess for bounded work, not a second Compose service by default.
- Container, dependency manifests/lockfiles, CI, security boundaries and deployment changes are maintainer-owned. Agents implement product features and tests within these constraints.
- No automatic cloud backup. The maintainer accepts complete data loss from host disk failure/deletion during experimentation; persistence must still survive ordinary container recreation.

## Consequences

Simplicity, portability, low operating cost and direct visibility of files. SQLite is unsuitable for independent multi-host writers or network-mounted database files. Local files and SQL must use hash-based immutable artifact staging plus DB commits; a file is not a transaction. Recoverable jobs must be persisted and submitted external effects cannot be replayed automatically after uncertainty.

## Reconsider only if measured

Multiple hosts/users, sustained writer contention, need for always-on remote execution, or a demonstrable operational need for offsite recovery. Write a new ADR before replacing the storage/process contract.

## Explicit v0.1 requirement disposition

`REQ-024` (automated backup/restore) and `REQ-026` (k3s target deployment) are **deferred by scope decision**, not implemented and not marked passed. `T22`/`T24` remain potential future checks. Other business/safety requirements remain in force.
