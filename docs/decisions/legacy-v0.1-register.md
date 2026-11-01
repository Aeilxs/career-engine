# Translated Legacy Decision Register (ADR-001–ADR-012)

These choices were **proposed** in the initial design study, not automatically accepted. They are recorded here in English for provenance and to make scope changes explicit. Accepted ADR-013 and ADR-014 override them where noted.

| ID | Original proposal | Alternative considered | Current interpretation |
|---|---|---|---|
| ADR-001 | Modular monolith | Microservices | **Consistent** with accepted single container |
| ADR-002 | SQL-backed bounded durable jobs | LangGraph/Temporal from day one | **Retained**; prove crash semantics in J1+/J6 |
| ADR-003 | Single-node SQLite | Initial PostgreSQL | **Accepted by ADR-013** for local host |
| ADR-004 | Separate read and submit connector capabilities | Universal ATS connector | **Retained**; explicit capability matrix |
| ADR-005 | Controlled Playwright integration | Fully autonomous browser agent | **Retained** for J5+ with a mock ATS first |
| ADR-006 | Immutable approved hash revisions | Overwriting generated files | **Retained**; approval tied to exact package |
| ADR-007 | XLSX is an export projection | Excel as business source of truth | **Retained**; canonical state in SQLite |
| ADR-008 | Narrow LLM port | General multi-agent framework | **Retained**; evaluate providers in P2 |
| ADR-009 | Replay persisted outputs | Regenerate on every retry | **Retained**; recorded costs and versions |
| ADR-010 | Ingestion record distinct from application | Automatically make application per import | **Retained**; J1 domain model |
| ADR-011 | CLI before minimal Web review | Full frontend SPA upfront | **Superseded** by ADR-014: Web-first React at J1; CLI still reuses services |
| ADR-012 | Try the existing CV generator after P3 | Rewrite immediately | **Retained** as a candidate, not verified integration |

See `docs/decisions/ADR-013-local-bootstrap.md` for the accepted no-k3s/no-S3/no-backup runtime and `ADR-014-vertical-milestones.md` for discovery sequencing. None of these records is implementation evidence.
