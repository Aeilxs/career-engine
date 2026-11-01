#!/usr/bin/env bash
# J0 proof: build, restart and read the same SQLite marker after container recreation.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null || { echo 'Docker CLI missing' >&2; exit 1; }
bash scripts/init-local.sh
docker compose build --pull
docker compose up -d --wait
marker="j0-$(date -u +%Y%m%dT%H%M%S)"
docker compose exec -T app career marker set "$marker"
docker compose down
docker compose up -d --wait
actual="$(docker compose exec -T app career marker get)"
if [[ "$actual" != *"$marker"* ]]; then
  echo "FAIL: marker did not survive recreation ($actual)" >&2
  exit 1
fi
curl --fail --silent http://127.0.0.1:8000/healthz >/dev/null
printf 'PASS J0: marker %s survived docker compose down/up\n' "$marker"
