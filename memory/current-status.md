# Current Status

Objective: use arXiv:2505.22954v3 as a real migration case for the writing harness.

Current branch: `case/arxiv-2505-22954`.

Current paper: Darwin Gödel Machine: Open-Ended Evolution of Self-Improving Agents.

Migration status:

- arXiv TeX source has been normalized into `paper/`.
- Core claims, evidence, numbers, references, citations, floats, terms, and notation have initial ledger entries.
- Release surfaces should be regenerated with `bash scripts/export-tex-release.sh` after paper edits.

Next entrypoint: read `ANATOMY.md`, `state/ccfa.yaml`, `.agent/session-protocol.md`, then this file.
