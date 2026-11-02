# J1 Stabilization Verification — 2026-11-02

**Status:** verification observed; maintainer acceptance remains pending.  
**Tested commit:** `4e4816c5ca6227715cd7642fe5b761e0a0e5546a`  
**Branch:** `copilot/fix-j1-sqlite-initialization`

## Runtime

- Python: 3.14.10
- SQLite: 3.53.1
- uv: 0.13.6
- Docker Engine: 28.0.4; Docker Compose: 2.38.2
- Browser: Playwright-managed Chromium 156.0.8078.4

## SQLite contention

Before the fix, a barrier-synchronized inline stress harness created a fresh DB for each of 20 rounds and started six initializer threads per round under Python 3.14.10. It recorded **4 `sqlite3.OperationalError: database is locked` failures**, in rounds 7, 11, 15 and 17. The same workload on Python 3.12.3 recorded zero failures.

After the fix, the same workload completed **20 rounds × 6 competing initializers with zero errors**. Each round reached schema version 3 and retained its J0 marker after another initialization. The committed regression is `tests/test_migrations.py::test_concurrent_initialization_is_safe`, which uses independent connections and a start barrier.

## Acquisition provenance counts

The multi-source integration regression begins with an empty database and object store:

| State | Offers | Revisions | Snapshots | Acquisitions | Backing objects |
|---|---:|---:|---:|---:|---:|
| Before imports | 0 | 0 | 0 | 0 | 0 |
| After same bytes from two provider/source identities | 2 | 2 | 1 | 2 | 1 |

Both acquisition records are queryable from their offer revisions and retain their own source reference, source ID, provider, board and retrieval timestamp. The offers remain distinct despite sharing a snapshot and backing object. A separate ten-import regression verifies one offer, one revision, one snapshot, one object and ten acquisition records.

Migration coverage includes a fresh database, J0 v1 upgrade with marker preservation, and v2→v3 acquisition backfill. The prior schema cannot recover acquisition-specific source references and retrieval times that were lost when identical content shared one snapshot. The backfill preserves each existing revision and uses the snapshot’s retained source reference/time plus the offer’s source identity; unavailable historical values are not invented.

## Commands and results

| Command | Exit | Result |
|---|---:|---|
| `$HOME/.local/bin/uv sync --frozen` | 0 | Locked project environment installed for Python 3.14 |
| `$HOME/.local/bin/uv run --frozen pytest -q tests/test_migrations.py tests/test_ingest_integration.py tests/test_api_j1.py` | 0 | 41 passed |
| `$HOME/.local/bin/uv run --frozen pytest -q` | 0 | 119 passed; one Starlette/httpx deprecation warning |
| `$HOME/.local/bin/uv run --frozen ruff check . && $HOME/.local/bin/uv run --frozen ruff format --check .` | 0 | All checks passed; 77 files already formatted |
| `$HOME/.local/bin/uv run --frozen mypy src` | 0 | No issues in 21 source files |
| `$HOME/.local/bin/uv run --frozen --with playwright playwright install chromium` | 0 | Installed the browser needed by the opt-in E2E |
| `$HOME/.local/bin/uv run --frozen --with playwright --with openpyxl python tests/e2e/j1_browser_e2e.py` | 0 | Process-kill/restart E2E: 56 passed, 0 failed |
| `$HOME/.local/bin/uv run --frozen --with playwright --with openpyxl python tests/e2e/j1_browser_e2e.py --mode docker` | 0 | Docker-recreation E2E: 56 passed, 0 failed |

The first E2E attempts exited 1 because the Playwright browser binary was absent; after installing Chromium, both commands above passed on the tested commit. Machine-readable results and ignored artifacts are under `reports/artifacts/J1-process-20261102T084242Z/` and `reports/artifacts/J1-docker-20261102T084242Z/`. No Docker, Compose, CI or dependency files were changed.

CodeQL reported zero Python or JavaScript alerts on the implementation commit. Secret scanning found no secrets in changed code or tests.
