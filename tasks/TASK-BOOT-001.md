# TASK-BOOT-001 — P0 Mac Runtime Qualification (Maintainer-Owned)

**State:** TODO / BLOCKED on genuine Python 3.14 resolution, Apple Silicon Docker build. **Owner:** human maintainer (agents may advise, no unreviewed runtime edit). **Gate:** J0.

## Work

1. Verify `uv` and install Python 3.14; resolve `uv.lock` from real package indexes, inspect it, commit it.
2. Run frozen install, Ruff, mypy, pytest; fix actual defects only, no acceptance weakening.
3. Validate Dockerfile image stages/architectures on Mac ARM64, Compose runtime invariants, localhost binding, non-root permissions and persistence of `./data`.
4. Run `scripts/verify-j0.sh` (build → marker → down/up → same marker) and inspect the J0 page.
5. Verify negative CI/test control: a deliberately broken assertion exits nonzero; restore and rerun.
6. Record real commands, versions, image ID, CPU/RAM footprint, limitations and artifacts under `reports/J0-<date>.md`.

## Acceptance

- J0 UI and `/healthz` accessible only at localhost.
- Genuine locked dependency graph installed and reviewed.
- All local tests and gates pass; marker persists through container recreation; no data deletion.
- A separate PR/commit for any runtime corrections, approved by maintainer.

**No business features, real network scraping or application submissions.**
