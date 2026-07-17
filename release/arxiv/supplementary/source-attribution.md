# Source Attribution

## arXiv Case

- arXiv id: `2505.22954`
- Title: Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents
- Authors: Jenny Zhang, Shengran Hu, Cong Lu, Robert Lange, Jeff Clune
- Abstract URL: https://arxiv.org/abs/2505.22954
- Source archive URL: https://arxiv.org/e-print/2505.22954
- Downloaded to: `/tmp/arxiv-2505.22954.6vL5kt/source` (disposable tmp dir, not committed)
- Archive sha256: `9ce27273d9175badbb14d1181bc6166c7afd5e7989ac274d3d5187413e19b9ed`
- Archive format: gzip-compressed tar (per `file`), extracted at `/tmp/arxiv-2505.22954.6vL5kt/extracted`
- arXiv-reported source mtime: 2026-03-16 (per gzip header; not a claim about paper publication date)
- Toplevel driver per `00README.json`: `main.tex`, compiler `pdflatex`, `texlive_version: "2025"`

## Human Gate

- Gate id: `external-source-migration` (per `.agent/capabilities/arxiv-case-harness-test.yaml`)
- Recorded by: automated case-harness-test run, case branch `case/arxiv-2505-22954`
- Recorded at: 2026-07-17

## Migration Mapping (mechanical, no invented facts)

Source repo is a single flat directory with `main.tex` as the sole top-level
driver (no `\input` of body sections — the paper's own sections are inline in
`main.tex`, with `\input` used only for large auxiliary content: appendix
task lists, diff patches, tool/prompt listings, and two ICLR-required
statements).

| Source | Template destination | Notes |
| --- | --- | --- |
| `main.tex` preamble packages (`iclr2026_conference`, `times`, `hyperref`, `url`, `booktabs`, `amsfonts`, `nicefrac`, `microtype`, `xcolor`, `ulem`, `titletoc`, `graphicx`, `amsmath`, `cleveref`, `multicol`, `tcolorbox`, `float`, `algorithm2e`, `subcaption`, `fvextra`, `adjustbox`) + `\lstdefinelanguage{Diff}`/`\lstset` + `\DefineVerbatimEnvironment` + `\crefname{algocf}...` | `paper/venue_preamble.tex` | Venue/class-bound setup, kept out of `paper/macros.tex` per `paper/ANATOMY.md` split. |
| `\newcommand{\fix}`, `\newcommand{\new}` | `paper/macros.tex` | Project-specific authoring aids, not reusable display macros. |
| `\title`, `\author`, `\iclrfinalcopy` | `paper/main.tex` | Kept in the main driver preamble, matching template convention. |
| `\maketitle` + footnote symbol setup for co-first/co-senior authors | `paper/sections/00_title.tex` | |
| `\begin{abstract}...\end{abstract}` | `paper/sections/01_abstract.tex` | |
| `\section{Introduction}` | `paper/sections/02_intro.tex` | Includes the `fig:conceptual` figure. |
| `\section{Related Work}` | `paper/sections/03_related.tex` | Body-only; "Additional Related Work" (part 2) is appendix content, see below. |
| `\section{Darwin Gödel Machine}` (`sec:methods`) | `paper/sections/04_method.tex` | |
| `\section{Experiments}` (`sec:experiments`) + all subsections + `\section{Safety Discussion}` (`sec:safety`) | `paper/sections/05_exp.tex` | No dedicated template slot exists for a standalone "Safety Discussion" section between Experiments and Conclusion (two-digit `NN_name` slots are exhausted between `05` and `06`); Safety Discussion is kept verbatim as a second `\section` inside the `05_exp.tex` wrapper rather than split or renumbered. Recorded as migration debt. |
| `\section{Conclusion and Limitations}` (`sec:conclusion`) | Split verbatim (no reworded/invented text) across `paper/sections/06_conclusion.tex` (opening + closing paragraphs) and `paper/sections/07_limitations.tex` (the two limitations paragraphs), to match the template's separate Conclusion/Limitations slots. Source only has one merged section; this is a structural split of existing text, not new content. |
| `\input{iclr_things/ethics_statement}`, `\input{iclr_things/reproducibility_statement}` | `paper/sections/09_statements.tex` (new slot; content copied verbatim from `paper/supplementary/iclr_things/*.tex`) | Source places these immediately after Conclusion and before Acknowledgments; the required template slot name `08_acknowledgement.tex` is fixed, so these statements are ordered after Acknowledgements in this migration (`09_statements.tex` follows `08_acknowledgement.tex`). Recorded as migration debt (front-matter ordering changed to fit fixed slot names, not a content change). |
| `\subsubsection*{Acknowledgments}` | `paper/sections/08_acknowledgement.tex` | |
| `\appendix` content: `\section{Additional Results}`, `\section{Additional Related Work}`, `\section{Algorithmic Details}`, `\section{Experiment Details}`, `\section{Benchmark Details}`, `\section{Best-Discovered Agents}`, `\section{Similar Target Functionality, Different Implementations}`, `\section{Case Study: Solving Hallucination}`, `\section{Additional Safety Discussion}`, `\section{Additional Future Work Directions}` | `paper/sections/10_appendix.tex` | Single appendix slot in the template; all appendix sections concatenated verbatim in source order. |
| `figures/*.pdf`, `solve_halluc/dgm_halluc.pdf` | `paper/figures/srcs/NN_name.pdf` | See figure numbering table below. |
| `main.bib` | `paper/refs.bib` | Renamed only; content untouched. |
| `iclr2026_conference.sty`, `iclr2026_conference.bst`, `fancyhdr.sty`, `natbib.sty` | `paper/style/` | Venue-provided class/style/bib-style files, placed alongside `paper/style/ccfa-paper.sty` per `paper/style/README.md` ("venue-provided `.sty`/`.cls`/`.bst` files may also be placed here ... once the paper is hard-bound to a specific venue class"). |
| `best_discovered_agent/`, `best_discovered_agent_polyglot/`, `diff_implementations/`, `initial_agent/`, `polyglot_tasks/`, `selfimprove_prompts/`, `solve_halluc/*.tex`, `swebench_tasks/`, `iclr_things/` | `paper/supplementary/<same-dir>/` | Copied verbatim, `\input` from `paper/sections/10_appendix.tex` (or `09_statements.tex` for `iclr_things/`) via paths relative to `paper/`. |

## Figure Numbering

| Wrapper/asset basename | Source file | Group |
| --- | --- | --- |
| `00_conceptual` | `figures/conceptual.pdf` | body |
| `01_dgm_comparisons_swe` | `figures/dgm_comparisons.pdf` | body (subfigure, paired with `02`) |
| `02_dgm_comparisons_polyglot` | `figures/dgm_comparisons_polyglot.pdf` | body (subfigure, paired with `01`) |
| `03_dgm_archive` | `figures/dgm_archive.pdf` | body (paired with `04`) |
| `04_dgm_progress` | `figures/dgm_progress.pdf` | body (paired with `03`) |
| `05_transfer_overview` | `figures/transfer_model_task.pdf` | body |
| `10_dgm_no_selfimprove` | `figures/dgm_wo_selfimprove.pdf` | appendix |
| `11_dgm_no_openended` | `figures/dgm_wo_openended.pdf` | appendix |
| `12_transfer_model_polyglot` | `figures/transfer_model_polyglot.pdf` | appendix |
| `13_dgm_halluc` | `solve_halluc/dgm_halluc.pdf` | appendix |

`01`/`02` and `03`/`04` are two-panel composite figures in the source (a
single `\begin{figure}` with two side-by-side images, each with its own
label). The `paper/figures/README.md` wrapper convention assumes one wrapper
`.tex` = one raw asset = one float. To avoid inventing a split-float layout
not in the source, these four assets are referenced with direct
`\includegraphics{figures/srcs/...}` inline in `paper/sections/05_exp.tex`
rather than through individual `NN_name.tex` wrapper files. Recorded as
migration debt / template-convention gap (see
`lab/harness-evals/20260717-arxiv-2505.22954-case-stress-round1.md`).

No claim, number, or citation facts were invented during this migration. All
prose, numbers, and citations in `paper/sections/*.tex` and
`paper/supplementary/` are copied verbatim from the arXiv source.
