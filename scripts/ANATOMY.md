# Scripts Anatomy

Small deterministic validators, indexers, exporters, and sync helpers.

- `paper_harness_checks.py`: shared validator backend. It owns schema, cross-reference, release-surface, and lightweight semantic checks used by the `check-*.py` wrappers.
- `report-numeric-exceptions.py`: JSON visibility report for numeric exception usage. It does not mutate the repo.
- `check-citation-review-worksheets.py`: validates optional citation sentence review worksheets against active TeX and ledger state.
- `report-citation-audit.py`: JSON visibility report for citation ledger coverage, paper locators, and audit status. It does not mutate the repo.
- `test-realkit-gate-negative.sh`: regression proof that `export_venue_template.py` hard-fails (never a false pass) when compiling against a broken venue-class stand-in; restores `state/conference-template.yaml` and removes `release/venue/` afterward.
