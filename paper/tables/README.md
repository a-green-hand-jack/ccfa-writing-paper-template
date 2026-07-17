# Tables

Every active table must be listed in `lab/artifacts/table-index.yaml`, bound to `state/float-placement-map.yaml`, and include source/generation provenance. Verified or final quantitative tables must reference numeric or result IDs.

## Naming convention

Table wrapper files use the same two-digit numeric prefix as figures: `NN_name.tex`.

- First digit: `0` = body table, `1` = appendix table.
- Second digit: order within that group, starting at `0`.
- `name` is a short lowercase snake_case slug (e.g. `main_results`, `ablation`).

Tables have no `srcs/` asset directory; content comes from `paper/generated/tables/`
or is authored inline. `scripts/check-figures-tables.py` enforces the naming pattern.
