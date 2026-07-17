#!/usr/bin/env bash
# Fidelity gate: compare the compiled paper PDF against the original source PDF.
#
# When migrating a real paper (arXiv case) into this template, the compiled
# `paper/main.tex` must reproduce the original faithfully. This script extracts
# text from both PDFs and reports an order-insensitive content diff plus a
# page-count check, so structural drift (dropped sections, invented prose,
# reordered content that shifts §/Table numbers) is caught instead of assumed.
#
# It is a heuristic, not a byte-exact comparator: it normalizes away page
# furniture (running headers/footers, page numbers, arXiv submission stamp) and
# de-duplicates lines before diffing. Non-zero content-only differences beyond
# the threshold fail the gate.
#
# Usage:
#   scripts/compare-original-pdf.sh <original> [compiled] [--threshold N]
#
#   <original>  arXiv id (e.g. 2605.03042), a PDF URL, or a local PDF path.
#   [compiled]  Path to our compiled PDF. Default: paper/main.pdf.
#               If missing, the script compiles paper/main.tex with latexmk.
#   --threshold N  Max allowed content-only differing lines per side
#                  (default 5) before the gate fails. The original's arXiv
#                  stamp line is always ignored.
#
# Exit codes: 0 = within threshold, 1 = drift exceeds threshold, 2 = setup error.
set -euo pipefail
cd "$(dirname "$0")/.."

ORIGINAL="${1:-}"
COMPILED="${2:-paper/main.pdf}"
THRESHOLD=5
# allow --threshold anywhere after the first arg
args=("$@")
for i in "${!args[@]}"; do
  if [ "${args[$i]}" = "--threshold" ]; then
    THRESHOLD="${args[$((i + 1))]:-5}"
  fi
done
# if second positional was actually a flag, restore default compiled path
case "$COMPILED" in --*) COMPILED="paper/main.pdf" ;; esac

if [ -z "$ORIGINAL" ]; then
  echo "ERROR usage: scripts/compare-original-pdf.sh <arxiv-id|url|path> [compiled.pdf] [--threshold N]" >&2
  exit 2
fi
for bin in pdftotext pdfinfo; do
  command -v "$bin" >/dev/null 2>&1 || { echo "ERROR $bin is required (poppler-utils)" >&2; exit 2; }
done

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# --- Resolve the original PDF -------------------------------------------------
ORIG_PDF="$WORK/original.pdf"
if [ -f "$ORIGINAL" ]; then
  cp "$ORIGINAL" "$ORIG_PDF"
elif [[ "$ORIGINAL" =~ ^https?:// ]]; then
  curl -fsSL "$ORIGINAL" -o "$ORIG_PDF"
elif [[ "$ORIGINAL" =~ ^[0-9]{4}\.[0-9]{4,5}(v[0-9]+)?$ ]]; then
  curl -fsSL "https://arxiv.org/pdf/${ORIGINAL}" -o "$ORIG_PDF"
else
  echo "ERROR could not resolve original '$ORIGINAL' (not a file, URL, or arXiv id)" >&2
  exit 2
fi
if ! head -c 5 "$ORIG_PDF" | grep -q '%PDF'; then
  echo "ERROR resolved original is not a PDF (got $(file -b "$ORIG_PDF" 2>/dev/null))" >&2
  exit 2
fi

# --- Resolve our compiled PDF -------------------------------------------------
if [ ! -f "$COMPILED" ]; then
  echo "INFO $COMPILED not found; compiling paper/main.tex" >&2
  command -v latexmk >/dev/null 2>&1 || { echo "ERROR latexmk required to build $COMPILED" >&2; exit 2; }
  (cd paper && latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex >"$WORK/latexmk.log" 2>&1) \
    || { echo "ERROR compile failed; see log tail:" >&2; tail -20 "$WORK/latexmk.log" >&2; exit 2; }
  COMPILED="paper/main.pdf"
fi

# --- Normalize text for order-insensitive comparison --------------------------
# Strip the arXiv submission stamp, pure page-number lines, squeeze whitespace,
# drop blanks, and de-duplicate (collapses repeated running headers/footers).
normalize() {
  pdftotext -nopgbrk "$1" - 2>/dev/null \
    | grep -vE '^arXiv:[0-9]{4}\.[0-9]{4,5}' \
    | grep -vE '^[0-9]+[[:space:]]*$' \
    | tr -s ' ' \
    | sed '/^[[:space:]]*$/d' \
    | sort -u
}
normalize "$COMPILED" >"$WORK/ours.norm"
normalize "$ORIG_PDF" >"$WORK/orig.norm"

OURS_ONLY="$WORK/ours_only.txt"
ORIG_ONLY="$WORK/orig_only.txt"
comm -23 "$WORK/ours.norm" "$WORK/orig.norm" >"$OURS_ONLY"
comm -13 "$WORK/ours.norm" "$WORK/orig.norm" >"$ORIG_ONLY"

n_ours=$(wc -l <"$OURS_ONLY")
n_orig=$(wc -l <"$ORIG_ONLY")
shared=$(comm -12 "$WORK/ours.norm" "$WORK/orig.norm" | wc -l)

# --- Page-count check ---------------------------------------------------------
pages_ours=$(pdfinfo "$COMPILED" 2>/dev/null | awk '/^Pages:/{print $2}')
pages_orig=$(pdfinfo "$ORIG_PDF"  2>/dev/null | awk '/^Pages:/{print $2}')

echo "=== PDF fidelity vs original ==="
echo "compiled : $COMPILED ($pages_ours pages)"
echo "original : $ORIGINAL ($pages_orig pages)"
echo "shared content lines : $shared"
echo "only in compiled     : $n_ours (invented / misplaced / reworded)"
echo "only in original     : $n_orig (dropped / reworded; arXiv stamp already ignored)"
echo "threshold per side   : $THRESHOLD"

status=0
if [ "$pages_ours" != "$pages_orig" ]; then
  echo "WARN page count differs ($pages_ours vs $pages_orig)"
fi
if [ "$n_ours" -gt "$THRESHOLD" ] || [ "$n_orig" -gt "$THRESHOLD" ]; then
  status=1
  echo
  echo "--- content only in COMPILED (first 40) ---"; head -40 "$OURS_ONLY"
  echo "--- content only in ORIGINAL (first 40) ---"; head -40 "$ORIG_ONLY"
fi

if [ "$status" -eq 0 ]; then
  echo "OK pdf-fidelity: within threshold"
else
  echo "FAIL pdf-fidelity: content drift exceeds threshold — reconcile paper/ with the original, then re-run"
fi
exit "$status"
