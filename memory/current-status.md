# Current Status

Objective: initialize evidence-first paper harness for `ccfa-paper-template`.

Next entrypoint: read `ANATOMY.md`, `state/ccfa.yaml`, `.agent/session-protocol.md`, then this file.

## Lane 3 (export/release) — arXivTeX-inspired hardening, 2026-07-17

Implements GitHub issues #10, #13, #12 (tracker #7), serially on one branch.

- **#10 arXiv export hardening**: `scripts/paper_harness_checks.py` `export_release()` now optionally
  latexpands `release/arxiv/main.tex` into a sibling `release/arxiv-flat/` (single-entry `main.tex` +
  `refs.bib` + style files + real figure/table assets, with `figures/srcs/`/`tables/srcs/` rewritten to
  flat `srcs/`). Tracked under `release/manifest.yaml`'s new `flatten` list (kept separate from
  `surfaces` so it never disturbs the existing byte-exact `paper/` <-> release surface freshness
  compare). Gracefully skipped (not failed) when `latexpand` is absent, and treated as a hard
  export-time failure when latexpand can't resolve an `\input` (a real hidden dependency). Added
  `scripts/check-latex.sh --compile-release [surface]` to compile the export directory itself (not
  `paper/`) — both the modular copy and, if present, `arxiv-flat/` — printing `UNVERIFIED` instead of a
  false pass when no TeX toolchain is present.
- **#13 LaTeX-safety policy + arXiv portability guardrail**: added `.agent/latex-policy.md` (harvested
  increment from arXivTeX's `AGENTS.md`, restated evidence-first; existing `.agent/*-policy.md` stubs
  were all identical placeholder boilerplate, so nothing there conflicted). Added
  `scripts/check-arxiv-portability.py` (folded into `check_release_package()`): flags non-standard
  fonts (`fontspec`/`\setmainfont`/...), absolute paths in `\input`/`\includegraphics`/`\graphicspath`/etc.,
  non-PDF/PNG/JPG figure assets, and project macros redefined inside a `.cls`/`.sty` file. Updated
  `.agent/checklists/latex.md`.
- **#12 Overleaf publish**: added `.github/workflows/overleaf-publish.yml` — `git subtree split
  --prefix=release/overleaf` pushed to an `overleaf` branch, gated by `check-release-package.py` +
  `check-release-freshness.py` + an explicit control-plane-leakage/symlink grep. Explicitly one-way
  (documented in `release/ANATOMY.md` and `.agent/release-policy.md`); no live badge added to this
  template's own `README.md` since its `paper/` is a placeholder skeleton, but a copy-paste "Open in
  Overleaf" badge snippet is documented for downstream projects. Verified locally with
  `git subtree split` against `release/overleaf`'s real git history (produced a clean tree, no leaked
  control-plane paths) — the actual GitHub Action push was not run since that requires the real remote.

Validators run and passing on this branch: `check-writing-harness.py`, `check-capability-parity.py`,
`check-anatomy-drift.py`, `export-tex-release.sh`, `check-release-package.py`,
`check-release-freshness.py`, `check-arxiv-portability.py`, `check-latex.sh --compile-release arxiv`,
`check-latex.sh --compile` (TeX Live 2026 available locally, so all of these were actually verified,
not just structurally checked).

Not verified: the `overleaf-publish.yml` GitHub Action itself was not executed against the real GitHub
remote (would require pushing/dispatching against the actual repo, which needs supervisor sign-off).

## Case arxiv-2505-22954 (Darwin Gödel Machine) — harness stress test, 2026-07-17

Branch `case/arxiv-2505-22954`. Migrated the full arXiv 2505.22954 LaTeX source into `paper/` (main.tex,
10 sections, 10 figure wrappers + srcs assets, refs.bib with 195 entries, venue style files, ~30
supplementary appendix fragments) and populated a minimal honest control plane (4 core claims, 1
external-evidence entry keyed to the arXiv source itself, 31 verified numbers across 5 groups, 184-entry
citation/reference ledgers bulk-imported at `fitness_status: needs-review`, 10 figures + 3 tables +
13 floats, worktrees/venue/ccfa metadata). Provenance in `paper/supplementary/source-attribution.md`.

All 7 declared validators pass clean on the committed tree: `check-capability-parity.py`,
`check-paper-populated.py`, `check-writing-harness.py`, `check-release-package.py`,
`check-release-freshness.py`, `check-conference-template.py`, `check-latex.sh --compile` (TeX Live 2026
available locally — full `pdflatex`/`bibtex` compile actually verified, not just structurally checked).
`research_project_harness validate --profile paper` is unavailable on this machine (no local
`research-project-harness` checkout) and was not run; every validator command above used the repo's own
`scripts/check-*.py` leaf checks instead.

Ran all 25 probes from `.claude/skills/arxiv-case-harness-test/references/stress-probe-catalog.md`
(catalog has 25 rows, not 26) against disposable `/tmp` copies. 20/25 caught cleanly. Two real misses:
- **P15 (numeric exception masking)**: a fabricated, unregistered numeric claim slipped past
  `check-numeric-consistency.py` because this migration's own `state/numbers/exceptions.yaml` date
  exceptions (`2024`/`2025`/`2026`) use unscoped `match_scope: literal` with no `path_pattern`. Case
  ledger debt — fixable locally, not an upstream gap.
- **P9 (citation fitness debt)**: `check-citation-fitness.py` passes on all 184 `needs-review` bulk
  citations as long as their per-citation locators aren't byte-identical; it verifies ledger
  *completeness*, not real fitness review. Documentation friction, matches the catalog's own prediction.

Two gates that work but ship inert by default: **P20** (worktree `physical_validation` absent by
default lets a nonexistent branch be marked `status: active`) and **P22** (venue-usage semantic check
is a no-op while `raw_template: TODO`, though `check-latex.sh --compile` independently catches the same
mutation). Full findings, exact mutations/commands/exit codes, and an upstream proposal sketch for P20
(no PR filed, no local `research-project-harness` checkout) are in
`lab/harness-evals/20260717-arxiv-2505.22954-case-stress-round1.md`.

Not verified: `research_project_harness validate --profile paper` (package absent locally);
`state/conference-template.yaml` real-kit compile verification (`raw_template` intentionally left
`TODO` with a `migration_exemption` note — no local ICLR 2026 official author kit available).
