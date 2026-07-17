#!/usr/bin/env bash
# Regression for the numeric-registry direct-field cross-check: the plain-number
# fields (value / display_value / reported_value) all denote the same reported
# scalar, so a `value: 1400` paired with `display_value: "1363"` is a fabrication
# and must fail. Before the fix, check_number_value_consistency lumped both into
# one direct_values list and only compared against the nested `display` dict, so
# a direct-vs-direct contradiction slipped through with exit 0. LaTeX-form fields
# (latex_value/macro_value) are deliberately NOT cross-checked because they hold
# macro forms like \num{1363} that are not bare-number comparable.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="$(PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
from scripts.paper_harness_checks import check_number_value_consistency
# fabrication must be caught
assert check_number_value_consistency("N", {"value": 1400, "display_value": "1363"}) == 1
# legit raw-vs-formatted must pass
assert check_number_value_consistency("N", {"value": 1363, "display_value": "1,363"}) == 0
# LaTeX macro form must not false-positive
assert check_number_value_consistency("N", {"value": 1363, "latex_value": "\\num{1363}"}) == 0
print("OK")
PY
)"
OUT="$(printf '%s\n' "$OUT" | tail -1)"

if [ "$OUT" != "OK" ]; then
  echo "ERROR test-numeric-direct-field-consistency-negative: direct-field contradiction not enforced as expected" >&2
  echo "$OUT" >&2
  exit 1
fi
echo "OK test-numeric-direct-field-consistency-negative: direct-field contradictions are caught, formatting variants pass"
