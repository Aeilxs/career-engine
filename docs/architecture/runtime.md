# Runtime and Repository Contracts

```text
Apple Silicon Mac / other local Docker host
  compose.yaml: exactly one service `app`, one image built from Dockerfile
    Python 3.14 / FastAPI / one Uvicorn worker
    React/Vite/TypeScript static build assets (J1+; no runtime Node server)
    app service + durable SQLite job-claim loop (J1+)
    SQLite WAL /data/career.db
    Immutable source objects and packages under /data
  local bind mount: ./data -> /data
  localhost port: 127.0.0.1:8000 -> container port 8000
```

**Currently implemented at J0:** GET `/`, GET `/healthz`, GET `/api/system/status`, CLI `career doctor`, `career marker set/get`, persistent SQLite marker table. These are infrastructure probes, *not* application-domain features. The J0 UI is intentionally static HTML; React is a reviewed J1 dependency change.

## Package boundaries

- `domain`: pure rules and value objects, no import of HTTP/browser/ORM/LLM frameworks.
- `application`: use cases, transactions, approval and transition enforcement.
- `infrastructure`: SQLite repositories, object files, job claim loop and exporters.
- `integrations`: read-only source connectors, LLM, renderer, ATS inspector/submitter.
- `web`: FastAPI routes and built frontend assets; CLI and HTTP call the same use cases.

Avoid one interface per class, generic event buses, multi-agent frameworks and speculative microservices. Add ports only where external boundaries vary or tests require them.

## SQLite and filesystem invariants

- DB resides on a local filesystem, **not NFS/SMB/S3**; avoid multi-host writes and separate pods sharing it.
- Connections per request/unit of work, `busy_timeout`, foreign keys, WAL, short transactional writes, explicit schema migrations after J0.
- SQL is the business authority; source bytes are immutable evidence; XLSX is a projection, never a source of truth.
- Write content-addressed objects to a temp file, fsync/close as needed, atomically rename to durable location, then commit SQL references/hashes; reconcile orphan objects after interruption. Do not claim DB+files are one atomic transaction.
- A logical job is `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED` or `BLOCKED`; leases and restart reconciliation required. An in-memory FastAPI BackgroundTask is not a durable worker.
- A submission attempt has a separate safety state machine. Failed confirmation must not trigger a generic job retry.

## Security and operations

- Bind to loopback only. Do not expose the API publicly without a new authentication/CSRF review.
- Default tests are offline and use synthetic profiles. HTML and URLs obtained from job posts are untrusted; never treat them as tool instructions.
- No secrets in source, screenshots, test fixtures, image layers, logs or PR comments.
- No cloud backups. Explicitly accepted risk: deletion of `./data` means loss of stored applications and evidence.
- Infrastructure files are maintainer-owned. Never add services, change privileges, or replace SQLite under an unrelated feature ticket.

## Build and portability

The `uv.lock` must be generated and reviewed on the target Mac during P0. CI runs lint, mypy, pytest, Compose syntax/runtime-contract checks and Docker build. Image architecture is **unverified until P0**. A later k3s deployment is possible only with a suitable local persistent volume and new ADR; not required to deliver J0–J7.
