#!/usr/bin/env bash
# Regression for case-declared body sections: a migrated paper renumbers its
# body sections to the source paper's real presentation order (so the compiled
# PDF reproduces the original section order — a fidelity requirement). The
# harness must therefore NOT mandate fixed body-section stems, only the framing
# anchors (00_title/01_abstract/10_appendix) plus the structural invariants
# (NN_name, body-before-appendix, ascending \input, inputs resolve). Asserts:
#   1. a renumbered ascending body layout PASSES;
#   2. a dangling \input (references a missing section file) FAILS;
#   3. a missing framing anchor FAILS.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="$(PYTHONDONTWRITEBYTECODE=1 python3 - "$(pwd)" <<'PY'
import importlib.util, sys, tempfile, pathlib
repo = pathlib.Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("ph", repo / "scripts/paper_harness_checks.py")
ph = importlib.util.module_from_spec(spec); sys.modules["ph"] = ph; spec.loader.exec_module(ph)

def evaluate(section_files, inputs_body, appendix="10_appendix"):
    root = pathlib.Path(tempfile.mkdtemp())
    ph.ROOT = root
    sec = root / "paper" / "sections"; sec.mkdir(parents=True)
    for f in ("macros.tex", "venue_preamble.tex"):
        (root / "paper" / f).write_text("")
    (root / "paper" / "refs.bib").write_text("")
    for s in section_files:
        (sec / (s + ".tex")).write_text("\\section{x}\n")
    body = "".join("\\input{sections/%s}\n" % s for s in inputs_body)
    main = body + "\\bibliography{refs}\n\\appendix\n\\input{sections/%s}\n" % appendix
    (root / "paper" / "main.tex").write_text(main)
    rc = ph.check_paper_surface() | ph.check_section_naming_and_order()
    return "PASS" if rc == 0 else "FAIL"

# 1. renumbered ascending body layout (non-canonical stems) -> PASS
r1 = evaluate(
    ["00_title", "01_abstract", "02_intro", "03_method", "04_exp", "05_related", "07_conclusion", "10_appendix"],
    ["00_title", "01_abstract", "02_intro", "03_method", "04_exp", "05_related", "07_conclusion"],
)
# 2. dangling \input to a missing section file -> FAIL
r2 = evaluate(
    ["00_title", "01_abstract", "02_intro", "10_appendix"],
    ["00_title", "01_abstract", "02_intro", "09_ghost"],
)
# 3. missing framing anchor (no 01_abstract input) -> FAIL
r3 = evaluate(
    ["00_title", "02_intro", "10_appendix"],
    ["00_title", "02_intro"],
)
print(r1, r2, r3)
assert r1 == "PASS", "renumbered ascending layout should PASS"
assert r2 == "FAIL", "dangling \\input should FAIL"
assert r3 == "FAIL", "missing framing anchor should FAIL"
print("OK")
PY
)"

if [ "$(printf '%s\n' "$OUT" | tail -1)" != "OK" ]; then
  echo "ERROR test-case-declared-sections-negative failed: $OUT" >&2
  exit 1
fi
echo "OK test-case-declared-sections-negative: renumbered body passes; dangling input and missing anchor fail"
