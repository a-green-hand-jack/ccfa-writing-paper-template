#!/usr/bin/env bash
# Negative-path regression for the venue-export action gate (#17): proves
# scripts/export-venue-template.sh hard-fails when compat.sty crashes under
# a broken venue-class stand-in, instead of a false pass. The stand-in is a
# synthetic minimal class built at runtime in a scratch dir -- never a
# vendored real venue kit -- with a \RequirePackage on a package that does
# not exist, simulating a real kit missing a dependency compat.sty needs.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v latexmk >/dev/null 2>&1; then
  echo "UNVERIFIED test-realkit-gate-negative: latexmk not installed, cannot exercise the compile hard-fail path"
  exit 0
fi

FIXTURE_DIR="$(mktemp -d)"
LOG="$(mktemp)"

cat > "$FIXTURE_DIR/brokenvenue.cls" <<'EOF'
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{brokenvenue}[2026/07/17 synthetic negative-test venue stand-in]
\LoadClass{article}
% Intentionally missing: a real venue kit ships every package it
% requires. This stand-in does not, so compilation must hard-fail.
\RequirePackage{ccfa-realkit-negative-test-missing-dependency}
EOF

TEMPLATE_BACKUP="$(mktemp)"
cp state/conference-template.yaml "$TEMPLATE_BACKUP"
trap 'rm -rf "$FIXTURE_DIR" "$LOG" release/venue; cp "$TEMPLATE_BACKUP" state/conference-template.yaml; rm -f "$TEMPLATE_BACKUP"' EXIT

if PYTHONDONTWRITEBYTECODE=1 python3 scripts/export_venue_template.py \
  --mode camera-ready --raw-template "$FIXTURE_DIR" >"$LOG" 2>&1; then
  echo "ERROR test-realkit-gate-negative: export-venue-template.sh should have hard-failed on a broken venue-class stand-in but exited 0" >&2
  cat "$LOG" >&2
  exit 1
fi

if ! grep -q "venue export failed to compile" "$LOG"; then
  echo "ERROR test-realkit-gate-negative: expected a compat.sty/venue-class compile failure message, got:" >&2
  cat "$LOG" >&2
  exit 1
fi

if grep -q "realkit-receipt" "$LOG"; then
  echo "ERROR test-realkit-gate-negative: a real-kit compile receipt must never be recorded for a failed compile" >&2
  exit 1
fi

if ! diff -q "$TEMPLATE_BACKUP" state/conference-template.yaml >/dev/null; then
  echo "ERROR test-realkit-gate-negative: state/conference-template.yaml was mutated by a failed compile" >&2
  exit 1
fi

echo "OK test-realkit-gate-negative: broken venue-class stand-in hard-failed as expected, no receipt recorded"
