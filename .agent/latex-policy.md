# LaTeX Policy

Scope: ccfa-paper-template evidence-first writing harness.

Harvested increment from arXivTeX's `AGENTS.md` LaTeX-safety guidance, restated so it does not
conflict with this repo's evidence-first invariants (a LaTeX fix never substitutes for a missing
claim, evidence, or numeric-registry entry).

- Keep repo facts in `state/`, `lab/`, `paper/`, `release/`, `human/`, or `memory/`.
- Do not promote claims, numbers, references, venue rules, or release files without the relevant ledger and gate.
- Update the nearest `ANATOMY.md` when changing structure.

## LaTeX safety

- Preserve the existing document class, package choices, macros, labels, and project conventions unless a change is necessary.
- Reuse existing commands instead of introducing duplicate macros; do not add a package for functionality already available in the project.
- Keep environments, braces, delimiters, and conditional blocks balanced; preserve valid escaping of LaTeX special characters.
- Keep labels stable unless their corresponding objects are removed or renamed; do not replace cross-references with hard-coded numbers.
- Do not manually edit generated files or compilation artifacts, and do not manually edit any `release/` export surface — see `.agent/release-policy.md` and `release/ANATOMY.md`: releases are rebuilt from `paper/` by `scripts/export-tex-release.sh`, so a LaTeX fix belongs in `paper/`, never in `release/arxiv/`, `release/arxiv-flat/`, `release/overleaf/`, or `release/github-tex/`.
- Do not change template or venue files (`paper/venue_preamble.tex`, official style files) unless explicitly requested; see `.agent/venue-policy.md`.
- Treat compilation warnings about undefined references, citations, duplicated labels, or malformed environments as issues to investigate, not to suppress.

## Compile verification

- A paper is not done because the source looks right; compile from the project's actual entry point (`paper/main.tex` via `scripts/check-latex.sh --compile`) and check for newly introduced LaTeX errors, undefined references, duplicated labels, or missing figures/files.
- Before publishing or handing off a release surface, also compile independently inside the export directory itself (not `paper/`) via `scripts/check-latex.sh --compile-release <surface>` — this is the only way to catch a dependency that only worked because it resolved against `paper/`'s surrounding tree.
- When no TeX toolchain is available, report the compile step as explicitly unverified (`UNVERIFIED`); never claim a pass that was not actually checked.

## arXiv portability guardrail

An arXiv-bound release surface must remain portable to a plain, standard TeX Live `pdflatex`
pipeline with no local machine state. Checked by `scripts/check-arxiv-portability.py` (folded into
`scripts/check-release-package.py`) and run alongside the independent compile gate:

- Use only standard TeX Live fonts and packages; avoid `fontspec`/`\setmainfont`/`\newfontfamily`, which assume system fonts and a XeLaTeX/LuaLaTeX toolchain instead of arXiv's classic `pdflatex` path.
- No absolute filesystem paths in `\input`, `\include`, `\includegraphics`, `\graphicspath`, `\bibliography`, `\usepackage`, or `\lstinputlisting` arguments — every path must resolve relative to the export surface itself.
- Prefer PDF, PNG, or JPG for figure and table assets over formats arXiv's pipeline handles less reliably (e.g. EPS, TIFF, BMP, raw SVG).
- Project-specific macros belong in `paper/macros.tex`, never redefined inside a reusable class or style file (`paper/style/*.cls`, `*.sty`) — that boundary is what keeps a missing-package failure easy to localize and fix.
