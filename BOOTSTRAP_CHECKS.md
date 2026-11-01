# P0 bootstrap acceptance checklist

These commands are **instructions**, not evidence that they have passed. Complete on the maintainer's Apple Silicon Mac before assigning J1.

```bash
uv --version
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
docker compose ps
docker image ls
```

Check the Docker image architecture, inspect the localhost-only binding, and confirm that marker state persists through `docker compose down` followed by `up -d --wait` without deleting `./data`. Record versions, resource measurements, a negative-test control and real results under `reports/J0-<date>.md`. Review and commit a genuine `uv.lock`, never a placeholder. Do not turn off CI to hide an unresolved lock.

Scope limitations: no production credentials, remote services, actual job submissions, cloud backup or React frontend are part of J0.
