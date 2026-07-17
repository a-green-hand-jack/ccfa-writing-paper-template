# Release Anatomy

Release surfaces are generated from `paper/` and must not expose harness state, Git metadata, or symlinks.
`release/manifest.yaml` records sha256, relpath, and size for exported files plus source revision data when available.

`release/arxiv-flat/` is an optional, generated sibling of `release/arxiv/`: a `latexpand`-flattened,
single-entry-point `main.tex` (plus `refs.bib`, style files, and any real figure/table assets, with
`figures/srcs/`/`tables/srcs/` paths rewritten to a flat `srcs/`). It is not a release surface in its own
right — it is tracked under `release/manifest.yaml`'s `flatten` list, not `surfaces` — and it is only
produced when `latexpand` is available. It exists to make hidden external dependencies (a missing
`\input` target, an asset that only resolved via a path outside the export surface) fail loudly at export
time instead of only after upload. `scripts/check-latex.sh --compile-release arxiv` independently compiles
both `release/arxiv/` and `release/arxiv-flat/` and reports `UNVERIFIED` rather than a false pass when no
TeX toolchain is present. Never hand-edit `release/arxiv-flat/`; fixes belong in `paper/` and the whole
tree is rebuilt by `scripts/export-tex-release.sh`.

## Publishing `release/overleaf` to an `overleaf` branch

`.github/workflows/overleaf-publish.yml` publishes the `release/overleaf` export surface to an
`overleaf` branch on push (when `release/overleaf/**` changes) or on manual `workflow_dispatch`. This
is **one-way publish only**: this repo is the source of truth, and edits made directly in Overleaf are
never read back. To bring an Overleaf edit into this repo, apply it under `paper/`, re-run
`scripts/export-tex-release.sh`, and let the workflow republish.

Design notes (arXivTeX comparison, tracked under sub-issue E / GitHub issue #12):

- arXivTeX's `overleaf-sync.yml` runs `git subtree split --prefix=main` because `main/` is itself the
  hand-edited, writable LaTeX source. Our `release/overleaf/` is a generated export surface, not a
  source directory, but `git subtree split` works identically on it: it only depends on the directory's
  git history, not on how it is edited, so the same mechanism applies without modification.
- Before splitting, the workflow runs `scripts/check-release-package.py` and
  `scripts/check-release-freshness.py` and an explicit control-plane-leakage/symlink grep as a
  CI-local defense-in-depth check, so a broken or stale export is never pushed to `overleaf`.
- The workflow reuses `scripts/export-tex-release.sh`'s guarantees (no `state/`, `lab/`, `memory/`,
  `.agent/`, `.claude/`, `.agents/`, `.git/`, `.github/`, or `human/` content, no symlinks) rather than
  re-implementing the release surface's forbidden-path policy in the Action itself.
- "Open in Overleaf" badge: Overleaf supports importing a GitHub branch via
  `https://www.overleaf.com/docs?snip_uri=<url-encoded zip URL>`, e.g. a link to
  `https://github.com/<owner>/<repo>/archive/refs/heads/overleaf.zip`. Because `release/overleaf/`
  becomes the branch root after the split (matching what Overleaf expects to unzip), this works without
  any further transformation. This template repo does not embed a live badge in its own `README.md`
  since its own `paper/` is a placeholder skeleton, not a real submission — downstream projects that
  populate `paper/` and enable this workflow should add:

  ```markdown
  [![Open in Overleaf](https://img.shields.io/badge/Open%20in-Overleaf-47A141)](https://www.overleaf.com/docs?snip_uri=https://github.com/<owner>/<repo>/archive/refs/heads/overleaf.zip)
  ```
