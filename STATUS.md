# Project status

**Prepared:** 2026-11-01. **State: J0 bootstrap candidate; P0 target-machine validation pending.**

| Work | State | Evidence / next action |
|---|---|---|
| English canonical specs | Prepared | `docs/spec`, `docs/quality`, `docs/decisions` and tasks in this release |
| Runtime model | Decision recorded | ADR-013: one container + SQLite + local files; not deployed on k3s |
| Milestone order | Decision recorded | ADR-014: source discovery at J2, before LLM and documents |
| Python/SQLite/API J0 tests | Preparation environment only | Run again with Python 3.14 on Mac ARM64; record commands and exits |
| Python 3.14 dependency resolution | **BLOCKED / P0** | Generate reviewed `uv.lock` on Mac; no lock shipped |
| Mac Docker build / restart E2E | **NOT RUN** | Run `scripts/verify-j0.sh`; Docker unavailable during preparation |
| J0 UI | Prepared | Standalone English HTML page; React/Vite target is J1 |
| Sample of 30 real relevant offers | TODO P1 | Human-selected sample before committing to an ATS connector |
| J1–J7 business runs | NOT IMPLEMENTED | Execute tickets in milestone order; do not claim live submission support |

Human approval is required before changing a row to `DONE`. Never infer acceptance from the presence of code or tests.
