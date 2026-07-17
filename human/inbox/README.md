# Inbox

Questions and materials awaiting human review.

## Case arxiv-2505-22954 stress round 1, 2026-07-17

For review: `lab/harness-evals/20260717-arxiv-2505.22954-case-stress-round1.md`
(full mutation-probe findings) and `paper/supplementary/source-attribution.md`
(migration mapping decisions, incl. the two-figure/two-notation-table split
forced by the wrapper naming convention, and the ethics/reproducibility
statement reordering forced by the fixed `08_acknowledgement` slot name).

Open items that need a human call, not a validator fix:
- `state/conference-template.yaml` `migration_exemption`: no local ICLR 2026
  official author kit was available to run a real-kit compile verification.
  Someone with kit access should eventually run
  `scripts/export-venue-template.sh --mode camera-ready` for real.
- `lab/research/citation-ledger.yaml` `fitness_review_status: pending`: all
  184 citations are bulk-imported at `needs-review`; a real sentence-level
  fitness pass has not been done (see P9 in the stress report).
