#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if [[ ! -d .git ]]; then echo 'Run git init first' >&2; exit 1; fi
git config --local core.hooksPath .githooks
chmod +x .githooks/commit-msg
echo 'Installed repository-local commit-msg hook via core.hooksPath=.githooks'
