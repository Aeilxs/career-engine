# Career Engine

**Status:** J0 implementation prepared; runtime approval on the maintainer's Mac is pending. This repository is not a completed job-application system.

Career Engine is a **local-first, single-user job discovery, preparation, review, and tracking application**. Each milestone provides a usable vertical slice and a repeatable end-to-end (E2E) proof. Automated submission is deferred until the local ATS simulator, approval, and lost-acknowledgment safety gates pass.

## Architecture we have chosen

- **One Docker image, one Docker Compose service, one localhost HTTP port.** FastAPI serves the API and, once implemented, the built React/Vite/TypeScript frontend. Node is a build-time tool, not a production service.
- **Python 3.14 + uv, SQLite WAL, and local files.** Bind-mount `./data` to `/data`; persist the database at `/data/career.db` and artifacts under `/data/`. Do not store the database inside the container layer.
- **One logical application and at most one durable job-claim loop** in the first implementation. No separate Redis, PostgreSQL, S3, k3s, Celery, message broker, or cloud backup.
- **Human approval before every real external submission.** No universal ATS submission claims or blind retries after uncertain outcomes.
- English for code, technical docs, agent instructions, task tickets, and initial UI. Product localization can be added later by an explicit task.

Architecture changes require a maintainer-approved ADR. Refer to [ADR-013](docs/decisions/ADR-013-local-bootstrap.md) and [ADR-014](docs/decisions/ADR-014-vertical-milestones.md).

## Starting from a freshly extracted ZIP

```bash
cd career-engine
uv python install 3.14
uv lock --python 3.14         # P0: resolve and review; then commit uv.lock
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src
uv run --frozen pytest -q
bash scripts/init-local.sh
python3 scripts/check-runtime-contract.py  # requires Docker Compose CLI
bash scripts/verify-j0.sh                   # builds, restarts, tests persistence
open http://127.0.0.1:8000
```

**P0 qualification is real work, not a formality.** The build environment used to prepare this ZIP had no package-index access, Python 3.14 interpreter, or Docker engine. Therefore **no `uv.lock` is included** and **no successful Docker/ARM64 build is claimed**. Resolve and commit the genuine lockfile on your Mac before opening a feature PR. The CI intentionally rejects a missing lockfile.

The `./data` directory is excluded from Git and Docker builds. `docker compose down` preserves its contents; deletion of that directory or disk failure does not. Offsite backups are deliberately out of scope for this prototype.

## Fast reference

| Purpose | File |
|---|---|
| Rules for coding agents | [`AGENTS.md`](AGENTS.md) |
| Collaboration, Conventional Commits | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Current implementation vs. unverified claims | [`STATUS.md`](STATUS.md) |
| Runtime and storage contract | [`docs/architecture/runtime.md`](docs/architecture/runtime.md) |
| Business requirements, unchanged IDs | [`docs/spec/requirements.md`](docs/spec/requirements.md) |
| Domain and connector contracts | [`docs/spec/contracts.md`](docs/spec/contracts.md) |
| Feasibility and discovery research | [`docs/spec/feasibility.md`](docs/spec/feasibility.md) |
| Risks, security, and operational constraints | [`docs/spec/risks.md`](docs/spec/risks.md) |
| Milestones and vertical demos | [`docs/architecture/roadmap.md`](docs/architecture/roadmap.md) |
| E2E runbooks J0–J7 | [`docs/quality/e2e-runs.md`](docs/quality/e2e-runs.md) |
| Requirements → tests mapping | [`docs/quality/test-matrix.md`](docs/quality/test-matrix.md) |
| Agent work items | [`tasks/`](tasks/) |
| Original design decision mapping | [`docs/decisions/legacy-v0.1-register.md`](docs/decisions/legacy-v0.1-register.md) |
| Agent assignment template | [`docs/agent/TEMPLATE_PROMPT.md`](docs/agent/TEMPLATE_PROMPT.md) |

## Running locally without Docker (development only)

```bash
uv run --frozen career serve --host 127.0.0.1 --port 8000
uv run --frozen career doctor
uv run --frozen career --version
```

Set `CAREER_DATA_DIR` to a temporary location if you do not want development work to touch `./data`. `career marker` is only a J0 persistence probe, **not** an application-domain feature. The current `/` UI is static; a React implementation belongs to J1 after frontend dependencies are reviewed.

## Git start

```bash
git init -b main                       # omit if already initialized
bash scripts/install-hooks.sh          # optional local Conventional Commits hook
git add .
git commit -m "chore: bootstrap career engine"
```

Do not commit `.env`, personal CVs, browser sessions, application responses, generated packages, or API credentials. For a conventional history, use branches such as `feat/j1-offer-ingestion` and commits like `feat(ingest): normalize manual job postings`.

## Source and scope reconciliation

This English repository is the **active specification**, derived from the supplied French v0.1 study and subsequent feasibility/milestone v0.2 discussion. The originals are not bundled as competing authoritative documentation. No original requirements have been silently treated as completed: see [requirement disposition](docs/spec/requirements.md), including deferred `REQ-024` and `REQ-026`. Past POC estimates are **plans, not measured results**.
