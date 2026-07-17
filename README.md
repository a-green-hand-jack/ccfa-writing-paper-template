# TODO Paper Title

Evidence-first paper repo for `ICLR 2027`.

## Entry Points

- Human summary: `PROJECT.md`
- Agent entry: `AGENTS.md`
- Structure map: `ANATOMY.md`
- Live writing state: `state/ccfa.yaml`
- Current status: `memory/current-status.md`

## Validate

```bash
rph validate --profile paper .
python scripts/check-writing-harness.py
python scripts/check-capability-parity.py
python scripts/check-paper-surface.py
bash scripts/export-tex-release.sh
python scripts/check-release-package.py
```

After importing a real paper, also run:

```bash
python scripts/check-paper-populated.py
bash scripts/check-latex.sh --compile
python scripts/check-release-freshness.py
python scripts/check-arxiv-portability.py
bash scripts/check-latex.sh --compile-release arxiv
```

The release directories are tex-only export surfaces. Do not edit them as the primary paper source.
Successful exports rewrite `release/manifest.yaml` with deterministic sha256, relpath, and size entries for each surface.

`release/arxiv-flat/` is an optional, `latexpand`-flattened, single-entry-point companion to
`release/arxiv/`, produced automatically by the export when `latexpand` is available (see
`release/ANATOMY.md`). `scripts/check-latex.sh --compile-release arxiv` compiles both directly inside
the export surface, independent of `paper/`, and reports `UNVERIFIED` instead of a false pass when no
TeX toolchain is present. `.github/workflows/overleaf-publish.yml` publishes `release/overleaf/` to an
`overleaf` branch on push; this is a one-way publish, not a live sync (see `release/ANATOMY.md`).
