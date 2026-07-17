# Anatomy Policy

Scope: ccfa-paper-template evidence-first writing harness.

- Keep repo facts in `state/`, `lab/`, `paper/`, `release/`, `human/`, or `memory/`.
- Do not promote claims, numbers, references, venue rules, or release files without the relevant ledger and gate.
- Update the nearest `ANATOMY.md` when changing structure.

## Paper file naming convention

`paper/sections/`, `paper/figures/`, and `paper/tables/` wrapper files use a
two-digit numeric prefix `NN_name.tex`: first digit `0`=body/`1`=appendix,
second digit=order within that group. Figure wrappers align basenames with a
raw asset under `paper/figures/srcs/` (e.g. `figures/00_teaser.tex` ↔
`figures/srcs/00_teaser.pdf`). See `paper/ANATOMY.md` for the full contract.
`scripts/check-anatomy-drift.py` and `scripts/check-figures-tables.py`
enforce this convention; do not rename these files without updating both
validators and `paper/main.tex`'s `\input` order.
