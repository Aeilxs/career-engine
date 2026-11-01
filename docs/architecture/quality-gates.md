# Quality Gates: Execution Evidence Over Green Narratives

## P0 — run on the actual development Mac

```bash
uv python install 3.14
uv lock --python 3.14
uv sync --frozen
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy src
uv run --frozen pytest -q
docker compose config -q
python3 scripts/check-runtime-contract.py
bash scripts/verify-j0.sh
```

Record tool versions, Mac architecture, image architecture, size, runtime memory, logs, HTTP `/healthz`, marker persistence and exits in `reports/J0-<date>.md`. Test a temporary failing assertion and show nonzero process exit code (then restore it). No result is passed without being observed. P0 uses real Docker, not an assumed configuration.

## Default automation

Unit + integration tests use temporary SQLite files and local fixtures, with no paid LLM, ATS, external websites, real accounts or personal profile data. API tests must exercise real business services; avoid mocking the persistence and transaction properties being tested. CI runs lint, formatting, mypy, pytest, Compose config, runtime contract and image build. UI/browser E2E requires a dedicated local simulator and is added at J1/J5 as appropriate.

## E2E acceptance matrix

| Gate | Deterministic result |
|---|---|
| J0 | Real HTTP UI/status; SQLite marker persists through down/up |
| J1 | Ten identical imports → 1 offer and 1 revision; changed content → R2; application and XLSX agree with SQL |
| J2 | Scan N new; repeated scan 0; changed snapshot → R2; failed source does not erase previous offers |
| J3 | Approved profile and offer → explained shortlist; missing criterion unknown; cached replay incurs 0 new calls |
| J4 | Selected offer → editable source/PDF; editing R1 creates R2; R1 approval no longer allows submit |
| J5 | Simulated form inspect/fill/readback; conditional field, file upload and missing required field handled; no submit |
| J6 | Simulated remote acceptance followed by lost response; after restart remote creation count remains exactly one |
| J7 | One selected real application explicitly authorized; proof or UNKNOWN recorded and reviewed |

**Mandatory for each milestone:** fixture or input provenance, commit SHA, exact command and exit code, timestamp, SQLite/artifact output, UI observation and limitations. A live verification must be a separate opt-in run, never required for offline CI.

## Submission-specific gate

All submit paths are disabled until J6 mock ATS tests pass. No retry, generic requeue or recovery may send a second request for an UNKNOWN attempt. A redirect, HTTP 200 or filled page is **not** a confirmed application. Proof is connector-specific; when proof cannot be established, remain UNKNOWN.
