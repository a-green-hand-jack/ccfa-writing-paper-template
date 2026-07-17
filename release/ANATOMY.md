# Release Anatomy

Release surfaces are generated from `paper/` and must not expose harness state, Git metadata, or symlinks.
`release/manifest.yaml` records sha256, relpath, and size for exported files plus source revision data when available.

`release/venue/` is a separate, gitignored preview surface produced by `scripts/export-venue-template.sh`
(pairs `paper/` with a locally supplied official venue kit). Unlike `arxiv/`, `overleaf/`, and `github-tex/`,
it is not checksum-manifested and is not one of the three declared release surfaces — regenerate it, don't commit it.
