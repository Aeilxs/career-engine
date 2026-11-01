# Maintainer Ownership and Architectural Change Review

## Human-owned surfaces

`Dockerfile`, `compose.yaml`, `.dockerignore`, `.python-version`, `pyproject.toml`, `uv.lock`, `.github/workflows/`, `.githooks/`, runtime-validation/bootstrap scripts, dependency selection, deployment/security boundaries and approved ADRs. Agents must request review before edits in these areas.

## Required proposal for a new dependency or infrastructure service

- Specific ticket and business property that requires it.
- Current solution's measured limitation and at least one simpler alternative.
- Dependencies (name/version/source/lock strategy), CPU/RAM/disk effects and ARM64 compatibility.
- Impact on Docker build, CI, persistence, security, restart recovery and test determinism.
- Migration/rollback approach and exact test commands.

**No speculative service additions**: Redis, Postgres, S3, Kubernetes, brokers, vector DB, and universal agent frameworks are out of the accepted bootstrap unless an ADR justifies them. The maintainer can choose to change the architecture; coding agents cannot silently make that decision.

## Approving agent work

Review changed tests, CI diff, new dependencies, failure cases, unknown submission handling and actual E2E artifacts. Reproduce critical commands on the Mac. Keep human-written edits. Small readable modules are preferred to clever abstractions.

## Git governance

Use Conventional Commits and narrowly scoped feature branches. The PR title must follow the same style for squash merges. The optional `.githooks/commit-msg` provides local early feedback; it is not a security boundary. Never use a green badge or task checkbox as acceptance evidence.
