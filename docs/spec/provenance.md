# Provenance and Superseded Study Documents

The canonical English specification was prepared from the candidate-provided **Career Engine design study v0.1** (originally 9 core documents, 12 legacy tasks, templates and agent instructions) and the **functional feasibility/E2E v0.2** analysis produced on 2026-11-01. The original documents were written primarily in French and contained partially superseded design assumptions.

To prevent agents from following contradictory historical directions, the legacy French Markdown files are **not bundled into this active English repository**. The originals remain with the user in the source archives. The active project retains traceability through the unchanged `REQ-001`–`REQ-027` and `T01`–`T25` IDs, P0–P6 POCs, risk IDs R01–R17, and the accepted ADRs.

### Notable changes from source plans

- Bootstrap stays local: one Docker image/service, SQLite and local files. The initially considered PostgreSQL/Garage/k3s architecture is **not** a bootstrap dependency.
- Automatic offsite backup/restore (`REQ-024`) and deployment to k3s (`REQ-026`) are **deferred**, not silently removed or claimed complete.
- Web-first React/Vite UI from J1 supersedes an earlier CLI/HTMX-first sequence; J0 remains static HTML.
- Real read-only discovery moves to J2, ahead of scoring, document generation and submission.
- The first live application is a one-off J7 pilot, not a promise of generic automation.

Where a detailed business rule in the source is not yet captured by the active docs, a human should explicitly add it via a `docs:` Conventional Commit before implementation. The translation/restructuring is **not** evidence of implementation or automated test coverage.
