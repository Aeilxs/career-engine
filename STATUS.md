# Project status

**Prepared:** 2026-11-01. **State: J0 bootstrap candidate; J1 implemented by an agent on branch `feat/j1-manual-ingest-to-xlsx`, awaiting maintainer review. Not accepted.**

| Work | State | Evidence / next action |
|---|---|---|
| English canonical specs | Prepared | `docs/spec`, `docs/quality`, `docs/decisions` and tasks in this release |
| Runtime model | Decision recorded | ADR-013: one container + SQLite + local files; not deployed on k3s |
| Milestone order | Decision recorded | ADR-014: source discovery at J2, before LLM and documents |
| Python/SQLite/API J0 tests | Preparation environment only | Run again with Python 3.14 on Mac ARM64; record commands and exits |
| Python 3.14 dependency resolution | **BLOCKED / P0** | Generate reviewed `uv.lock` on Mac; no lock shipped |
| Mac Docker build / restart E2E | **NOT RUN** | Run `scripts/verify-j0.sh`; Docker unavailable during preparation |
| J0 UI | Superseded in J1 | The static J0 page was replaced by the J1 UI; its API status line is kept |
| Sample of 30 real relevant offers | TODO P1 | Human-selected sample before committing to an ATS connector |
| J1 manual import → tracker → XLSX | **Implemented, NOT ACCEPTED** | Observed on commit `df5a0b9`: ruff/format/mypy/pytest (115 passed) exit 0; browser E2E 56/56 in process-kill mode and in Docker container-recreation mode. See `reports/J1-2026-11-01.md` for commands, hashes and limitations |
| J1 frontend toolchain (React/Vite/TypeScript) | **NOT DONE — needs maintainer prerequisite** | J1 UI is dependency-free vanilla JS served by FastAPI; no dependency, lock, Dockerfile or CI file was changed |
| J1 XLSX library | **Decision needed** | XLSX is written with a small stdlib (`zipfile`) writer; verified by an independent reader and by `openpyxl` in the E2E; never opened in Excel/LibreOffice/Numbers |
| J1 browser E2E in CI | NOT WIRED | Opt-in script `tests/e2e/j1_browser_e2e.py` uses ephemeral `uv run --with playwright --with openpyxl`; CI workflow is maintainer-owned and unchanged |
| J2–J7 business runs | NOT IMPLEMENTED | Execute tickets in milestone order; do not claim live submission support |

Human approval is required before changing a row to `DONE`. Never infer acceptance from the presence of code or tests.
