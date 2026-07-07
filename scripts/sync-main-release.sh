#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/export-tex-release.sh
python3 scripts/check-worktrees.py
echo "OK sync-main-release"
