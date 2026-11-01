#!/usr/bin/env bash
# Local bind-mount ownership setup; never overwrites an existing .env.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p data
if [[ ! -f .env ]]; then
  printf 'CAREER_UID=%s\nCAREER_GID=%s\n' "$(id -u)" "$(id -g)" > .env
  chmod 600 .env
  echo 'Created local .env with current UID/GID'
else
  echo 'Keeping existing local .env; check CAREER_UID/CAREER_GID if /data is not writable'
fi
