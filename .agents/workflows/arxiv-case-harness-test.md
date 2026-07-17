# arxiv-case-harness-test

Purpose: migrate a real arXiv TeX source into `ccfa-writing-paper-template`,
populate the evidence-first control plane, stress-test the template, and land any
durable fixes in this repository. This repository is the standalone source of
truth; there is no upstream to feed findings back to.

Source capability: `.agent/capabilities/arxiv-case-harness-test.yaml`. Read it
first and treat it as the contract for this run.

For destructive probe ideas, read
`.claude/skills/arxiv-case-harness-test/references/stress-probe-catalog.md`
after the case compiles and baseline validators pass.

## Inputs

- arXiv id, abstract URL, or downloaded source archive.
- This repository (template or case repo):
  `/home/user/Projects/ccfa-writing-paper-template`.
- Existing paper harness files under `paper/`, `state/`, `lab/`, `release/`,
  `.agent/`, `.claude/`, `.agents/`, and `scripts/`.

## Declared Outputs

- `paper/`
- `state/`
- `lab/research/`
- `lab/artifacts/`
- `lab/harness-evals/`
- `release/`
- `memory/current-status.md`
- `human/inbox/README.md`

## Validators

For a full migration or replay, run the repository's self-contained validators:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-capability-parity.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-paper-populated.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-writing-harness.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-release-package.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-release-freshness.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-conference-template.py
PYTHONDONTWRITEBYTECODE=1 bash scripts/check-latex.sh --compile
```

If compile is blocked by environment or package state, record the blocker and
continue with every non-compile validator that can run.

## Operating Steps

1. Orient: confirm `pwd`, `git status -sb`, remotes, branch, and current sync
   base. For a new case branch, use `git switch -c case/arxiv-<id> origin/main`.
2. Fetch source into `/tmp`, using `https://arxiv.org/e-print/<id>` or a
   user-provided archive. Do not unpack directly over `paper/`.
3. Normalize TeX mechanically into `paper/main.tex`, `paper/sections/`,
   `paper/figures/`, `paper/style/`, `paper/refs.bib`, `paper/macros.tex`,
   `paper/venue_preamble.tex`, and `paper/supplementary/`.
4. Record provenance in `state/ccfa.yaml` and
   `paper/supplementary/source-attribution.md`. Do not infer paper facts from
   chat when the source or repo lacks evidence.
5. Populate the smallest honest set of ledgers in `state/`, `lab/research/`,
   and `lab/artifacts/`: claims, evidence, results, numbers, citations,
   references, floats, notation, terminology, venue metadata, and worktrees.
6. Export release surfaces with `scripts/export-tex-release.sh` after paper
   source and ledgers are coherent.
7. Run the full baseline validator set. Commit the first clean migration
   separately from stress reports.
8. Stress only disposable `/tmp` copies. For each probe, record mutation,
   expected contract, commands, actual diagnostics, classification, and follow-up
   in `lab/harness-evals/YYYYMMDD-arxiv-<id>-case-stress-roundN.md`.
9. For a harness gap, branch off `main` here, implement the validator/template
   fix, add a negative regression test when practical, validate, commit, and open
   a PR with base `main`.
10. After the fix merges, merge `origin/main` into the case branch, replay the
    original probe, and append the result.

## Fix PR Path

```bash
git fetch origin
git switch -c fix/<short-gap-name> origin/main
# edit validator/template/docs/tests under scripts/, .agent/, .claude/, .agents/
gh pr create --base main --head fix/<short-gap-name>
```

Persistent template, validator, docs, workflow, and CI behavior lives in this
repository under `scripts/`, `.agent/`, `.claude/`, `.agents/`, and the template
surfaces. There is no separate generated-template source to keep in sync.

## Completion Contract

- Source capability reviewed:
  `.agent/capabilities/arxiv-case-harness-test.yaml`.
- Migration provenance is recorded in repo files.
- Baseline validation and relevant leaf checks pass, or blockers are recorded.
- Destructive probes ran in `/tmp` copies.
- Stress findings are written to `lab/harness-evals/`.
- Harness fixes land on a branch in this repository and target `main` through a
  pull request.
