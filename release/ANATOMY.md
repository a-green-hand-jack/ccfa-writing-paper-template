# Release Anatomy

Release surfaces are generated from `paper/` and must not expose harness state, Git metadata, or symlinks.
`release/manifest.yaml` records sha256, relpath, and size for exported files plus source revision data when available.
