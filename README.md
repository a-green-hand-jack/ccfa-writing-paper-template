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
bash scripts/export-tex-release.sh
python scripts/check-release-package.py
```

The release directories are tex-only export surfaces. Do not edit them as the primary paper source.
