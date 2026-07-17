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
