#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -f paper/main.tex
test -f paper/macros.tex
if [ "${1:-}" = "--compile" ]; then
  if ! command -v latexmk >/dev/null 2>&1; then
    echo "ERROR latexmk is required for --compile" >&2
    exit 2
  fi
  OUT="$(mktemp -d)"
  trap 'rm -rf "$OUT"' EXIT
  (cd paper && latexmk -cd -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir="$OUT" main.tex >/tmp/paper-harness-latexmk.log)
  echo "OK latex-compile"
  exit 0
fi
echo "OK latex-surface"
