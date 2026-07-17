# Figures

Every active figure must be listed in `lab/artifacts/figure-index.yaml`, bound to `state/float-placement-map.yaml`, and include source/generation provenance.

## Naming convention

Figure wrapper files use a two-digit numeric prefix: `NN_name.tex`.

- First digit: `0` = body figure, `1` = appendix figure.
- Second digit: order within that group, starting at `0`.
- `name` is a short lowercase snake_case slug (e.g. `teaser`, `pipeline`).

Each wrapper's basename must match a raw asset under `figures/srcs/` with the
same basename, e.g. `figures/00_teaser.tex` wraps `\includegraphics` of
`figures/srcs/00_teaser.pdf` (or `.png`/`.jpg`/`.jpeg`). `scripts/check-figures-tables.py`
enforces both the naming pattern and the wrapper-to-asset basename alignment.
