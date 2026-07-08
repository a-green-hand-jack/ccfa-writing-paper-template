---
name: arxiv-case-harness-test
description: Migrate arXiv TeX sources into the CCFA evidence-first writing template, populate the paper/state/lab/release control plane, run mutation-based harness stress tests, and prepare upstream research-project-harness feedback or PRs. Use when testing ccfa-writing-paper-template with a real arXiv paper case, replaying a case against a newly synced template, or turning template friction into upstream harness changes.
---

# arxiv-case-harness-test

Purpose: turn a real arXiv paper into a reusable stress case for
`ccfa-writing-paper-template`, then use the case to test whether the template
and upstream paper harness enforce evidence-first writing contracts.

Source capability: `.agent/capabilities/arxiv-case-harness-test.yaml`. Read it
first and treat it as the path and validator contract for this run.

For destructive probe ideas, read
`.claude/skills/arxiv-case-harness-test/references/stress-probe-catalog.md`
after the case compiles and baseline validators pass.

## Repository Roles

- Generated template or case repo:
  `/home/user/Projects/ccfa-writing-paper-template`.
- Upstream harness repo:
  `/home/user/Projects/research-project-harness`.
- Permanent template, validator, and workflow fixes belong in upstream on the
  `ccfa-writing-paper-template` branch, not as hand-edited generated-template
  code.
- Case-specific paper migration, ledgers, reports, and replay notes belong in a
  case branch such as `case/arxiv-2505-22954`.

## Inputs

- arXiv abstract URL or id, for example `https://arxiv.org/abs/2505.22954`.
- Downloaded arXiv source archive or `https://arxiv.org/e-print/<id>`.
- Existing template files under `paper/`, `state/`, `lab/`, `release/`,
  `.agent/`, `.claude/`, `.agents/`, and `scripts/`.
- Upstream harness checkout when proposing validator or template fixes.

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

Run the relevant leaf checks and the upstream profile. For a full migration or
post-sync replay, use:

```bash
PYTHONPATH=/home/user/Projects/research-project-harness/src \
  PYTHONDONTWRITEBYTECODE=1 python3 -m research_project_harness validate --profile paper .

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-capability-parity.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-paper-populated.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-writing-harness.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-release-package.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-release-freshness.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-conference-template.py
PYTHONDONTWRITEBYTECODE=1 bash scripts/check-latex.sh --compile
```

If compilation depends on missing TeX packages or external assets, record the
blocker in `lab/harness-evals/` and still run every non-compile validator that
can execute.

## Workflow

### 1. Orient

Confirm the current repo, branch, remote, and cleanliness:

```bash
pwd
git status -sb
git remote -v
```

If starting a new case, branch from the generated template mainline:

```bash
git fetch origin
git switch -c case/arxiv-<id> origin/main
```

If replaying an existing case after a template sync, merge or rebase the latest
generated template branch into the case branch, then validate before editing.

### 2. Fetch and Normalize arXiv Source

Download into a temporary directory first. Do not unpack directly over `paper/`.

```bash
CASE_ID=2505.22954
TMP=$(mktemp -d "/tmp/arxiv-${CASE_ID}.XXXXXX")
curl -L "https://arxiv.org/e-print/${CASE_ID}" -o "$TMP/source"
file "$TMP/source"
```

Unpack according to `file` output (`tar`, `gzip`, or plain TeX bundle). Preserve
source provenance in `paper/supplementary/source-attribution.md` or a nearby
supplementary metadata file.

Map the source into the template surface:

- main driver: `paper/main.tex`
- section files: `paper/sections/*.tex`
- figures: `paper/figures/`
- tables or generated macros: `paper/tables/` and `paper/generated/`
- style files: `paper/style/`
- bibliography: `paper/refs.bib`
- reusable macros: `paper/macros.tex`
- venue glue: `paper/venue_preamble.tex`
- raw-source notes or README metadata: `paper/supplementary/`

Keep the migration mechanical first. Do not invent claim, number, or citation
facts while moving files.

### 3. Populate the Control Plane

Fill the smallest honest set of ledgers needed for validators and future stress
testing:

- `state/ccfa.yaml`: title, short title, owner/authors, venue, paper type,
  source URL, release surfaces.
- `state/conference-template.yaml` and `state/venue-profile.yaml`: declared
  venue and local template artifact.
- `state/claim-evidence-map.yaml` and `state/evidence-matrix.csv`: paper-facing
  claims and their support state.
- `state/numeric-registry.yaml`, `state/numbers/macros.yaml`, and
  `state/numbers/groups/*.yaml`: reported numbers, macros, derived values, and
  exceptions.
- `lab/research/citation-ledger.yaml` and
  `lab/research/reference-ledger.yaml`: active citations and imported BibTeX
  keys.
- `lab/artifacts/result-index.yaml`, `lab/artifacts/figure-index.yaml`, and
  `lab/artifacts/table-index.yaml`: result, figure, and table provenance.
- `state/float-placement-map.yaml`: active labels, assets, references, and
  result/claim/numeric bindings.
- `state/notation.yaml` and `state/terminology.yaml`: active notation and terms.
- `release/manifest.yaml`: generated release surfaces and source revision.

Use bulk-import states such as `needs-review` when necessary, but make that
state explicit and report it as migration debt.

### 4. Export and Baseline

Export release surfaces only after the paper source and ledgers are coherent:

```bash
PYTHONDONTWRITEBYTECODE=1 bash scripts/export-tex-release.sh
```

Run the validators listed above. Commit the first clean migration separately
from stress reports so later sync/replay diffs are easy to read.

### 5. Stress the Harness

Run destructive probes only in disposable copies:

```bash
TMP=$(mktemp -d /tmp/ccfa-case-probe.XXXXXX)
cp -a /home/user/Projects/ccfa-writing-paper-template/. "$TMP/"
cd "$TMP"
# mutate files here, then run the target validator and profile
```

For each probe, record:

- mutation: exact file and field changed;
- expected contract: what should fail and why;
- commands: validator/profile commands and exit codes;
- actual result: caught, missed, noisy, or false positive;
- classification: upstream harness gap, generated template gap, case ledger
  debt, documentation friction, or accepted regression fixture;
- follow-up: PR, issue, case cleanup, or no action.

Write the report to:

```text
lab/harness-evals/YYYYMMDD-arxiv-<id>-case-stress-roundN.md
```

### 6. Feed Findings Upstream

For an upstream harness gap, work in `/home/user/Projects/research-project-harness`
from the paper product branch:

```bash
cd /home/user/Projects/research-project-harness
git fetch origin
git switch -c agent/<short-gap-name> origin/ccfa-writing-paper-template
```

Fix the validator, template source, docs, or generated workflow in upstream.
Add focused tests or eval fixtures when practical. Validate locally, commit, and
open the PR against `ccfa-writing-paper-template`:

```bash
gh pr create \
  --repo a-green-hand-jack/research-project-harness \
  --base ccfa-writing-paper-template \
  --head agent/<short-gap-name>
```

After merge and template sync, return to the case branch, merge the generated
template update from `origin/main`, replay the original probe, and append the
result to the same `lab/harness-evals/` report or a follow-up round.

If the fix is not ready, still record a precise upstream proposal in the stress
report with the failing mutation and the command that currently passes.

## Completion Contract

- Source capability reviewed:
  `.agent/capabilities/arxiv-case-harness-test.yaml`.
- Migration contract: arXiv provenance is recorded, TeX source is normalized
  into `paper/`, and control ledgers describe the migrated paper without relying
  on chat memory.
- Baseline contract: profile validation and relevant leaf checks pass, or every
  blocker is recorded with command output.
- Probe contract: destructive mutations happen in `/tmp` copies, not in the live
  case branch.
- Upstream contract: persistent template or validator changes are proposed
  against `research-project-harness` branch `ccfa-writing-paper-template`.
- Handoff contract: the final response names commits, reports, validators run,
  unresolved case debt, and any upstream PR or proposal.
