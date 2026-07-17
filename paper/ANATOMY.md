# Paper Anatomy

LaTeX source lives here. It is not the source of truth for claims, numbers, references, or release policy.

## File naming convention

`paper/sections/`, `paper/figures/`, and `paper/tables/` wrapper files use a
two-digit numeric prefix: `NN_name.tex`.

- First digit: `0` = body content, `1` = appendix content.
- Second digit: order within that group, starting at `0` (e.g. `00`, `01`, `02`, ...).
- `name` is a short lowercase snake_case slug.

`paper/main.tex` inputs body sections in ascending `0`-prefixed order before
`\appendix`, then appendix sections in ascending `1`-prefixed order after it.

Figure wrappers additionally align basenames with a raw asset in
`paper/figures/srcs/`: `figures/00_teaser.tex` wraps
`figures/srcs/00_teaser.pdf` (or `.png`/`.jpg`/`.jpeg`). `paper/figures/srcs/`
holds only raw figure assets, never generated wrapper `.tex` files.

`scripts/check-anatomy-drift.py` and `scripts/check-figures-tables.py`
enforce this naming and the wrapper-to-asset alignment; see
`.agent/anatomy-policy.md` for the doctrine-level record.
