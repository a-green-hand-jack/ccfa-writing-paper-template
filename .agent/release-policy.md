# Release Policy

Scope: ccfa-paper-template evidence-first writing harness.

- Keep repo facts in `state/`, `lab/`, `paper/`, `release/`, `human/`, or `memory/`.
- Do not promote claims, numbers, references, venue rules, or release files without the relevant ledger and gate.
- Update the nearest `ANATOMY.md` when changing structure.
- Publishing a release surface to an external host (an `overleaf` branch, an arXiv upload) is one-way: the external copy is never a second source of truth. Apply any edit made externally under `paper/` first, then re-export; see `release/ANATOMY.md` and `.github/workflows/overleaf-publish.yml`.
