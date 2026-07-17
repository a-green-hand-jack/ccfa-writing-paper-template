# Float Placement Policy

Scope: ccfa-paper-template evidence-first writing harness.

- Keep repo facts in `state/`, `lab/`, `paper/`, `release/`, `human/`, or `memory/`.
- Do not promote claims, numbers, references, venue rules, or release files without the relevant ledger and gate.
- Update the nearest `ANATOMY.md` when changing structure.

## Renaming figure/table wrapper files

`lab/artifacts/figure-index.yaml` and `lab/artifacts/table-index.yaml`
entries reference floats by `label`/`float_id`, not by wrapper filename, so
renaming a wrapper to the `NN_name.tex` convention (see `paper/ANATOMY.md`)
does not by itself break `state/float-placement-map.yaml` bindings. If a
rename also changes a figure's `\includegraphics` asset path or a table's
`path`/`asset_path` field, update the corresponding index entry in the same
change so `scripts/check-figures-tables.py` keeps passing.
