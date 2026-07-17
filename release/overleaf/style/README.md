# Style Files

`ccfa-paper.sty` is the Writing-owned, reusable Class API. It carries only
presentation logic that does not depend on this paper's specific claims,
numbers, or references, so it can be dropped, swapped for a venue
`compat.sty` shim, or reused by another paper without edits. Project-specific
macros (anything tied to this paper's terminology, numbers, or notation)
belong in `paper/macros.tex`, not here — that split is what lets a future
arXiv "missing package" repair or venue conversion move a single macro
in or out without touching paper prose.

`paper/main.tex` loads it with `\usepackage{style/ccfa-paper}`.

Venue-provided `.sty`/`.cls`/`.bst` files may also be placed here after
license and source checks, once the paper is hard-bound to a specific
venue class.

## Class API

| Macro | Purpose |
| --- | --- |
| `\parahead{text}` | Bold run-in paragraph heading, e.g. `\parahead{Setup} We first ...` |
| `\headbf{text}` | Bold (optionally accent-colored) inline heading text |
| `\figref{label}` | `Figure~\ref{label}` |
| `\tabref{label}` | `Table~\ref{label}` |
| `\algref{label}` | `Algorithm~\ref{label}` |
| `\eqnref{label}` | `Equation~\eqref{label}` |
| `\tablestyle{colsep}{stretch}` | Sets `\tabcolsep`, `\arraystretch`, centers, and shrinks to `\small` for compact tables |
| `\cmark` / `\xmark` | Check mark / cross mark (via `pifont`) for compact yes/no table cells |
| `x{<pt>}`, `y{<pt>}`, `z{<pt>}` | Fixed-width centered / left / right column types (in points) |
| `P{<width>}` | Centered column type for an arbitrary width (e.g. `P{2cm}`) |
| `Y` | Centered `tabularx` fraction-width column, for use inside a `tabularx` environment |
| `\papercolor{blue\|slate\|forest}` | Optional: switch the accent color used by `\headbf`/`\parahead` |
| `\paperstyle{accent\|plain}` | Optional: enable/disable the accent color (defaults to `accent`) |

## Boundary

- Reusable display macros: `paper/style/ccfa-paper.sty`.
- Project-specific macros (terminology, notation, paper-only shortcuts): `paper/macros.tex`.
- If arXiv rejects a package this style depends on, the fix is scoped to this file, not to `paper/sections/*.tex`.
