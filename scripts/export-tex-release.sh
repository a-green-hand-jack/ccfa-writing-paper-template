#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHONDONTWRITEBYTECODE=1 python3 scripts/paper_harness_checks.py export_release
