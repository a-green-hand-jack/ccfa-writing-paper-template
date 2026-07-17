# arXiv 2604.01658 (CORAL) — migration baseline record

Case branch: `case/arxiv-2604-01658`. Lane: migration (authoring) only.
Destructive stress probes are out of scope for this run (baseline + fidelity only).

## Source

- arXiv 2604.01658v1 "CORAL: Towards Autonomous Multi-Agent Evolution for Open-Ended Discovery"
- COLM 2026 preprint venue kit (`colm2026_conference`).
- Provenance recorded in `paper/supplementary/source-attribution.md` and `state/ccfa.yaml`.

## Fidelity gate (compare-original-pdf.sh 2604.01658)

- compiled `paper/main.pdf`: 27 pages
- original `2604.01658`: 27 pages
- shared content lines: 1612
- only in compiled (invented/misplaced/reworded): 0
- only in original (dropped/reworded): 1  (threshold per side: 5)
- Result: `OK pdf-fidelity: within threshold`
- The single residual original-only line is page furniture / appendix section
  numbering noise (source compiles the appendix without `\appendix`, so appendix
  sections are numbered continuously; the template uses `\appendix`). No paper
  content was dropped, invented, or reworded. Section `\input` order in
  `paper/main.tex` is ascending per the anatomy convention; the empty
  (fully-commented) `07_limitations` slot renders nothing, so its position
  relative to `06_conclusion` does not change the compiled PDF.

## Migration debt (needs-review ledger state)

1. **Numeric registry bulk-import.** CORAL is results-heavy: its Experiments and
   Appendix sections report ~250 distinct source-stated numeric literals
   (per-task scores, kernel cycle counts, percentages, cost/efficiency figures).
   These are accepted in bulk via a path-scoped entry in
   `state/numbers/exceptions.yaml` (reason documents the bulk-import) rather than
   individually registered. Only the two headline kernel scores (1363 -> 1103)
   are registered as verified numbers. `state/numeric-registry.yaml` status is
   `partial-migration-debt`. Follow-up: individual number registration / numeric
   macro generation if this case is promoted beyond a harness fixture.
2. **Citation fitness.** All 43 cited keys are bulk-imported into
   `lab/research/citation-ledger.yaml` / `reference-ledger.yaml` with
   `fitness_status: needs-review` (`fitness_review_status: pending`). Sentence-level
   citation fitness was not audited during mechanical migration.
3. **Figure convention gap.** The source `fig:coral-ui` groups two subfigures in
   one float; the one-wrapper=one-asset anatomy convention cannot express this, so
   the float stays inline in `10_appendix.tex` and the two assets
   (`12_ui1.png`, `13_ui2.png`) get comment-only alignment stub wrappers.
4. **Venue kit verification.** `state/conference-template.yaml` carries a
   `migration_exemption`: no local real COLM 2026 author kit exists on this
   machine, so the venue class cannot be realkit-verified; the class/bst are
   copied verbatim from the arXiv source's own build.

## Validators run

See the migration commit message and the handoff for the full command/exit-code list.

## Harness-gap finding (observed, NOT fixed on this case branch)

- **Probe/trigger:** `scripts/check-latex.sh --compile-release arxiv` (proactively
  run; not part of the required validator set).
- **Observed:** the modular `release/arxiv` surface compiles cleanly, but
  `release/arxiv-flat` fails with `! LaTeX Error: File 'style/ccfa-paper.sty' not
  found.` at `main.tex:3`.
- **Root cause:** `compute_flatten_bundle()` in `scripts/paper_harness_checks.py`
  copies `style/*.sty|*.bst` into the flat bundle root (dropping the `style/`
  directory), but `rewrite_flatten_asset_paths()` only rewrites `figures/srcs/` /
  `tables/srcs/` -> `srcs/`. It does not rewrite the `style/` prefix in
  `\usepackage{style/...}` / `\bibliographystyle{style/...}`. The base template's
  own `paper/main.tex` ships `\usepackage{style/ccfa-paper}`, so the flat surface
  cannot resolve the style package for ANY case, not just this one.
- **Classification:** harness gap (flatten path-rewriter incomplete), pre-existing
  and template-wide; exposed by this real-paper case.
- **Follow-up:** durable fix belongs on a dedicated `fix/...` branch off `main`
  (out of scope for this migration lane): teach `rewrite_flatten_asset_paths()` (or
  the flatten copier) to also rewrite `style/<name>` -> `<name>` in `\usepackage`
  and `\bibliographystyle`, with a negative regression test. Not fixed here; scripts
  are read-only for the case branch. The required validators (six Python checks +
  `check-latex.sh --compile` on `paper/`) and the mandatory `compare-original-pdf.sh`
  fidelity gate all pass; the modular `release/arxiv` surface compiles.
