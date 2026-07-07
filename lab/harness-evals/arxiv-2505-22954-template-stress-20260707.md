# arXiv:2505.22954 Template Stress Report

Date: 2026-07-07

Case repo/worktree: `/home/user/Projects/ccfa-writing-paper-template-stress-arxiv-2505-harness-20260707`

Branch: `stress/arxiv-2505-harness-20260707`

Base case commit: `726a429 Apply numeric exception upstream fix to arXiv case`

Upstream harness reference: `/home/user/Projects/research-project-harness` at `e7ef260`.

## Purpose

Use the migrated arXiv:2505.22954 case as a realistic stress target for the generated `ccfa-writing-paper-template`. This run is not a happy-path validation. It intentionally mutated disposable copies under `/tmp` to test whether the harness catches plausible drift in claims, evidence, numbers, citations, floats, release surfaces, and notation.

The real worktree was kept report-only. Destructive probes were run on `/tmp/ccfa-stress-probe-*` copies made from `git archive HEAD`; those disposable copies are execution evidence, not repository artifacts.

## Baseline

The unmodified stress worktree passed the current harness and LaTeX checks before mutation probing:

```text
PYTHONPATH=/home/user/Projects/research-project-harness/src PYTHONDONTWRITEBYTECODE=1 python3 -m research_project_harness validate --profile paper .
OK: paper harness valid

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-writing-harness.py
OK writing_harness

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-paper-populated.py
OK paper_populated

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-numeric-consistency.py
OK numeric_consistency

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-citation-fitness.py
OK citation_fitness

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-figures-tables.py
OK figures_tables

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-release-freshness.py
OK release_freshness

./scripts/check-latex.sh --compile
OK latex-compile
```

## Mutation Probe Matrix

| Probe | Mutation / action | Expected behavior | Actual behavior | Verdict | Friction | Upstream implication |
| --- | --- | --- | --- | --- | --- | --- |
| Claim/evidence drift | Added `E-MISSING-PROBE` to `C-DGM-SWEBENCH-IMPROVEMENT` in `state/claim-evidence-map.yaml`. | `check-claim-evidence.py` should fail on unknown evidence. | Failed: `ERROR claim C-DGM-SWEBENCH-IMPROVEMENT references unknown evidence E-MISSING-PROBE`. | Caught. | Clear and localized. | This contract is doing real work. Keep it as a regression fixture. |
| Verified non-macro numeric drift | Changed registered `N-TRANSFER-POLYGLOT-CLAUDE35-BASE` from `32.0\\%` to `32.1\\%` while paper text still says `32.0\\%`. | `check-numeric-consistency.py` should fail because the paper literal no longer matches the verified registry. | Failed: `ERROR unregistered numeric literal in populated paper content: 32.0\\% at paper/sections/appendix.tex:43`. | Caught. | Error says "unregistered" rather than "registered value drift"; still actionable. | The upstream `e7ef260` fix for verified non-macro literals works. A nicer drift-specific diagnostic would help. |
| Numeric exception default scope | Added fake line `Claude 3.5 probe achieved 77.7\\%...` and an exception with pattern `Claude 3\\.5` but no `match_scope`. | Default literal scope should not excuse the same-line fake metric. | Failed: `ERROR unregistered numeric literal ... 77.7\\% at paper/sections/intro.tex:24`. | Caught. | This directly verifies the earlier context-wide exception bug is fixed. | Keep default `match_scope: literal`; require explicit context matching. |
| Numeric exception path gate | Added fake `77.7\\%` in intro plus an exact literal exception scoped to `path_pattern: ^paper/sections/appendix\\.tex$`. | The exception should not apply outside its path. | Failed: `ERROR unregistered numeric literal ... 77.7\\% at paper/sections/intro.tex:24`. | Caught. | Good new affordance; the case has not yet used it for task ids / diff fragments. | Convert broad task-id and Git-diff exceptions to `path_pattern`-scoped exceptions. |
| Citation ledger mismatch | Removed the `citation-ledger` entry for active cited key `GoogleDeepMind2025GeminiThinking`. | A citation validator should fail because paper content cites a key that is no longer in the citation ledger. | `check-citation-fitness.py` passed: `OK citation_fitness`. `check-reference-existence.py` failed: `ERROR paper cites key not registered in citation-ledger: GoogleDeepMind2025GeminiThinking`. | Caught only by adjacent validator. | The split between "reference existence" and "citation fitness" is easy to misuse; running only citation fitness gives a false sense of coverage. | Either make `check-citation-fitness.py` include the active citation-key coverage precondition, or rename/document the split very loudly in workflows. |
| Table result binding drift | Removed `result_ids`/`numeric_ids` from first verified table in `lab/artifacts/table-index.yaml`. | `check-figures-tables.py` should fail for verified/final quantitative table with no numeric/result binding. | Failed: `ERROR table tab-DGM-greedy verified/final without numeric_ids or result_ids`. | Caught. | Clear for quantitative tables. Configuration tables remain awkward. | Add table `kind` such as `quantitative`, `qualitative`, `configuration`. |
| Release surface leakage | Created `release/arxiv/state/leak.txt`. | `check-release-package.py` should fail for harness/state path leakage and manifest mismatch. | Failed with leakage and unmanifested-file errors. | Caught, noisy. | Parent/child leakage paths plus manifest mismatch produce repeated same-category noise for one bad file. | Deduplicate release-package errors by surface/path/category. |
| Notation conflict | Added a second `DGM` notation entry with a different meaning. | `check-notation.py` should fail on conflicting symbol definitions. | Failed: `ERROR notation symbol has conflicting meanings: DGM`. | Caught. | Good conflict check. It still does not prove registered notation is actually used or first defined at the right semantic location. | Add optional usage/first-definition scanning for active notation. |

## Constructive Workflow Probes

### Numeric Registry Capability

Read `numeric-registry` capability and workflow without mutating the case. The real case has 32 entries in `state/numbers/groups/appendix.yaml`, but the capability contract does not mention `state/numbers/groups/*.yaml` or `state/numbers/exceptions.yaml` in declared outputs / allowed paths.

Command evidence:

```text
rg -n "state/numbers/groups|exceptions.yaml" .agent/capabilities/numeric-registry.yaml .agents/workflows/numeric-registry.md
<no matches>

rg -c '"numeric_id"' state/numbers/groups/appendix.yaml
32
```

Friction: the generated capability tells an agent to update only declared outputs, but a realistic migrated paper stores many verified numbers in group files outside those outputs. This makes a careful agent stop or write a blocker instead of doing the obvious ledger maintenance.

Upstream implication: include `state/numbers/groups/*.yaml` and, where appropriate, `state/numbers/exceptions.yaml` in numeric-registry inputs/outputs/allowed paths, or clarify that group files are read-only generated/indexed surfaces.

### Reference Audit Capability

The reference workflow validators pass, but the migration state is low signal: all 184 citation-ledger entries are `needs-review` and share the same generic context.

Command evidence:

```text
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-capability-parity.py
OK capability_parity

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-reference-existence.py
OK reference_existence

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-citation-fitness.py
OK citation_fitness

citation entries: 184
fitness statuses: {'needs-review': 184}
unique contexts: 1
context count: 184
Migrated from arXiv:2505.22954v3 TeX source; sentence-level citation fitness not audited in this case branch.
```

Friction: this is formally honest, but the validator pass can be mistaken for citation fitness rather than migration provenance.

Upstream implication: add first-class `bulk_import_status` / `migration_source` semantics and separate "coverage exists" from "citation is fitness-reviewed".

## Prioritized Upstream Fixes

### Validator Bugs Or Gaps

1. Make `check-citation-fitness.py` either call the active citation-key coverage checks from `check-reference-existence.py`, or emit a warning that it assumes reference existence already passed. The citation-ledger mismatch probe showed direct `check-citation-fitness.py` can pass after an active cited key is removed from the citation ledger.
2. Add path-scoped numeric exception fixtures to upstream tests and migrate this case's SWE-bench task-id / Git-diff exceptions to `path_pattern` entries.
3. Deduplicate release-package leakage and manifest errors. The leakage probe reports repeated same-category noise for one leaked `release/arxiv/state/leak.txt` file.
4. Add optional active notation usage / first-definition validation. The conflict check works, but usage correctness is still mostly structural.

### Workflow And Documentation Friction

1. Update `numeric-registry` capability outputs/allowed paths to include `state/numbers/groups/*.yaml` and clarify when non-macro verified numbers belong in groups versus the primary index.
2. Add migration-aware reference workflow language: "bulk imported from arXiv source, coverage checked, fitness not audited" should be a distinct state from true citation fitness.
3. Add table kind classification so configuration tables do not need fake result bindings.
4. Decide which capability owns harness-eval/stress reports. The current report path is useful but not owned by a capability output contract.

### Case-Specific TODOs

1. Convert current broad numeric exceptions for raw SWE-bench task ids and supplementary Git diff fragments to `path_pattern`-scoped exceptions.
2. Replace the generic 184-entry citation context with staged citation audit buckets, or explicitly mark the whole ledger as `bulk_import_status: needs-review`.
3. Revisit `tab:fm-hyperparam`: it is a configuration table and should not need a result binding once table kinds exist.

## Final Check Plan

After this report is written, rerun:

```text
PYTHONPATH=/home/user/Projects/research-project-harness/src PYTHONDONTWRITEBYTECODE=1 python3 -m research_project_harness validate --profile paper .
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-writing-harness.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-paper-populated.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-numeric-consistency.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-citation-fitness.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-figures-tables.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-release-freshness.py
./scripts/check-latex.sh --compile
```

Final results should be appended below before commit.

## Final Check Results

Final checks passed after writing this report:

```text
PYTHONPATH=/home/user/Projects/research-project-harness/src PYTHONDONTWRITEBYTECODE=1 python3 -m research_project_harness validate --profile paper .
OK: paper harness valid

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-writing-harness.py
OK writing_harness

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-paper-populated.py
OK paper_populated

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-numeric-consistency.py
OK numeric_consistency

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-citation-fitness.py
OK citation_fitness

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-figures-tables.py
OK figures_tables

PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-release-freshness.py
OK release_freshness

./scripts/check-latex.sh --compile
OK latex-compile
```
