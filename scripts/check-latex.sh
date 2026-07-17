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
if [ "${1:-}" = "--compile-release" ]; then
  # Fixes belong in paper/ only; release/<surface> is a fully rebuildable export
  # surface, so this gate never mutates it and never falls back to paper/.
  SURFACE="${2:-arxiv}"
  SURFACE_DIR="release/$SURFACE"
  if [ ! -f "$SURFACE_DIR/main.tex" ]; then
    echo "ERROR release surface main.tex not found: $SURFACE_DIR/main.tex (run scripts/export-tex-release.sh first)" >&2
    exit 2
  fi
  if ! command -v latexmk >/dev/null 2>&1; then
    echo "UNVERIFIED latex-compile-release: latexmk not installed, cannot verify $SURFACE_DIR"
    exit 0
  fi
  TARGETS=("$SURFACE_DIR")
  if [ -f "$SURFACE_DIR-flat/main.tex" ]; then
    TARGETS+=("$SURFACE_DIR-flat")
  fi
  for TARGET in "${TARGETS[@]}"; do
    OUT="$(mktemp -d)"
    LOG="$(mktemp)"
    if ! (cd "$TARGET" && latexmk -cd -pdf -interaction=nonstopmode -halt-on-error -file-line-error -outdir="$OUT" main.tex) >"$LOG" 2>&1; then
      echo "ERROR latex-compile-release failed for $TARGET (log: $LOG)" >&2
      tail -n 40 "$LOG" >&2
      rm -rf "$OUT"
      exit 1
    fi
    rm -rf "$OUT" "$LOG"
  done
  echo "OK latex-compile-release: ${TARGETS[*]}"
  exit 0
fi
echo "OK latex-surface"
