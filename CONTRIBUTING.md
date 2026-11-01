# Contributing

This is a maintainer-led project that uses coding agents to implement scoped business features. A change must be reviewable, reproducible, and independently testable.

## Workflow

1. Select one ticket from `tasks/` and read the required REQ/ADR/test references.
2. Create a dedicated branch, e.g. `feat/j1-manual-import`.
3. Write or identify the failing acceptance test, implement the minimum vertical slice, and re-run all relevant tests.
4. Provide a PR using `.github/PULL_REQUEST_TEMPLATE.md` with an actual E2E report and precise exit codes.
5. Request human approval for any change to pinned infrastructure, locks, dependencies, submission behavior, or acceptance criteria.
6. Merge after review; only then may the maintainer mark the milestone `DONE` in `STATUS.md`.

## Conventional Commits

Format: `type(optional-scope)!: imperative summary` (e.g. `feat(offers): add content-hashed imports`). Lowercase types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `style`, `revert`. Use a `BREAKING CHANGE:` footer when appropriate. Prefer focused changes, not enormous agent-generated commits.

Examples:

```text
chore: bootstrap local runtime
feat(offers): persist normalized source revisions
fix(export): escape spreadsheet formula prefixes
test(submission): reject replay after unknown outcome
docs(adr): record SQLite persistence decision
```

Optional hook: `bash scripts/install-hooks.sh`. The CI validates PR titles (so squash merges stay conventional). The hook is a convenience, **not** a substitute for code review.

## Definition of Ready

Assigned ticket has a scope, REQ IDs, deterministic fixtures, measurable acceptance criteria and a runnable E2E scenario. Changes to runtime/dependencies are handled by a separate, reviewed prerequisite. An unapproved POC is not a product feature.

## Definition of Done

- Behavior observable through the real interface and/or CLI, backed by SQLite and actual files as specified.
- Happy path, failure path, idempotency, concurrency and restart tests where relevant.
- No weaker existing tests; no network calls in the default suite.
- Lint, typecheck, tests, container smoke checks and relevant E2E all **actually** run and their outcomes recorded.
- E2E report stored under `reports/` with commit ID, fixture, commands, exit codes, snapshots, limitations and human sign-off.
- Documentation and STATUS updated; no secrets, private documents or cookies committed.

## Review priorities

1. Safety of external effects and permission boundaries.
2. Correctness of persistent data, migration and approval semantics.
3. Deterministic tests and honest evidence.
4. Readable code, small interfaces and straightforward debugging.

The maintainer retains the right to edit any code. Do not modify human-owned changes merely to satisfy a preferred agent style.
