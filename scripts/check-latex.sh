#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f paper/main.tex
test -f paper/macros.tex
echo "OK latex-surface"
