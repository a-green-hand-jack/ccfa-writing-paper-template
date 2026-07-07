# Darwin Gödel Machine

Evidence-first paper repo for `ICLR 2026`, populated with the arXiv:2505.22954v3
TeX source as a migration and harness test case.

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
python scripts/check-claim-evidence.py
python scripts/check-numeric-consistency.py
python scripts/check-reference-existence.py
python scripts/check-float-placement.py
bash scripts/export-tex-release.sh
python scripts/check-release-package.py
```

After importing a real paper, also run:

```bash
python scripts/check-paper-populated.py
bash scripts/check-latex.sh --compile
python scripts/check-release-freshness.py
```

The release directories are tex-only export surfaces. Do not edit them as the primary paper source.
Successful exports rewrite `release/manifest.yaml` with deterministic sha256, relpath, and size entries for each surface.
