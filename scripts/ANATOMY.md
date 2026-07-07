# Scripts Anatomy

Small deterministic validators, indexers, exporters, and sync helpers.

- `paper_harness_checks.py`: shared validator backend. It owns schema, cross-reference, release-surface, and lightweight semantic checks used by the `check-*.py` wrappers.
