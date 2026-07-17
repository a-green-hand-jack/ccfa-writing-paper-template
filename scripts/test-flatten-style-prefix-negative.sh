#!/usr/bin/env bash
# Regression for the arxiv-flat style-prefix rewrite: the flattener copies
# style/*.{cls,sty,bst} to the flat bundle ROOT, so any `{style/NAME}`
# reference in the flattened main.tex (\usepackage, \documentclass,
# \bibliographystyle) must lose its `style/` prefix or the flat surface
# fails to compile for EVERY case. This proves rewrite_flatten_asset_paths
# drops that prefix; before the fix the prefix survived and LaTeX could not
# find the package at the flat root.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="$(PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from scripts.paper_harness_checks import rewrite_flatten_asset_paths
src = (
    "\\documentclass{article}\n"
    "\\usepackage{style/ccfa-paper}\n"
    "\\bibliographystyle{style/plainnat}\n"
    "\\includegraphics{figures/srcs/fig1.pdf}\n"
)
out = rewrite_flatten_asset_paths(src)
assert "style/" not in out, f"style/ prefix survived: {out!r}"
assert "\\usepackage{ccfa-paper}" in out, out
assert "\\bibliographystyle{plainnat}" in out, out
# unrelated asset rewrite still works and is untouched by the style pass
assert "figures/srcs/fig1.pdf".replace("figures/", "") in out or "srcs/fig1.pdf" in out, out
print("OK")
PY
)"

if [ "$OUT" != "OK" ]; then
  echo "ERROR test-flatten-style-prefix-negative: rewrite did not drop the style/ prefix" >&2
  echo "$OUT" >&2
  exit 1
fi
echo "OK test-flatten-style-prefix-negative: flatten rewriter drops the style/ prefix"
