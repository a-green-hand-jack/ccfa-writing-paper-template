# Stress Probe Catalog

Use this catalog after the migrated arXiv case has a clean baseline. Run probes
in disposable `/tmp` copies. Keep one probe focused enough that a pass/fail
result identifies a single contract.

## Core Probe Matrix

| Area | Mutation | Expected validator behavior |
| --- | --- | --- |
| Claim numeric drift | Change a core claim literal, for example `50.0%` to `60.0%`, without changing numeric ledgers or evidence. | `check-numeric-consistency.py` or profile should fail. |
| Claim numeric binding | Rebind a claim's `numeric_ids` to numbers from another claim. | Numeric or claim/result checks should reject non-reciprocal bindings. |
| Result claim drift | Rebind a verified result to the wrong `claims_supported`. | `check-result-status.py` or profile should fail. |
| Result numeric drift | Remove a verified result's numeric id or remove the numeric group's reciprocal `result_id`. | Result/numeric checks should fail. |
| Evidence status drift | Make a verified result depend only on planned, dropped, or contradictory evidence. | Claim/evidence/result checks should fail. |
| Active citation coverage | Remove an active cited key from `lab/research/citation-ledger.yaml`. | Reference existence or citation fitness should fail. |
| Reference ledger coverage | Remove or downgrade the active reference ledger row for a cited key. | Reference/citation checks should fail. |
| BibTeX coverage | Delete a cited key from `paper/refs.bib`. | Reference existence should fail. |
| Citation fitness debt | Mark all active citations as generic bulk import without review. | Validator may pass; report as workflow friction if semantic fitness is not actually audited. |
| Figure asset drift | Change an active `\includegraphics` target while leaving label ledgers unchanged. | Figure/table or float-placement checks should fail. |
| Unregistered active float | Add an included TeX file with a new figure/table label and no ledger entry. | Float-placement and profile should fail. |
| Table result binding | Remove result or numeric bindings from a verified table. | Figure/table checks should fail. |
| Notation line drift | Point `first_defined` to a line that no longer contains the symbol. | Notation check should fail. |
| Unregistered notation | Add a new active symbol in included TeX without `state/notation.yaml`. | Notation check should fail if the symbol is in scope for active-use rules. |
| Numeric exception masking | Add an unrelated active numeric literal near a broad exception. | Numeric check should fail unless the exception is explicitly scoped. |
| Release freshness | Edit `paper/sections/*.tex` without exporting release surfaces. | `check-release-freshness.py` and profile should fail. |
| Release leakage | Add `state/`, `lab/`, or `.agent/` content under a release surface. | `check-release-package.py` should fail. |
| Manifest contract | Change manifest version, checksum algorithm, surface source, or surface path. | Release package should fail. |
| Manifest source revision | Change `source_revision.commit` or `tree` away from paper source. | Release package/freshness should fail. |
| Worktree physical state | Mark a missing branch/path as active-like in `state/worktrees.yaml`. | Worktree check should fail. |
| Venue binding | Change declared venue or template artifact without changing paper template usage. | Conference template check should fail. |
| Venue usage | Remove or bypass the venue style input in active `paper/main.tex`. | Conference template check should fail. |
| Anonymity | Enable anonymous mode while active title/authors still identify authors. | Anonymity check should fail. |
| Active TeX graph | Add bad citations/numbers/labels in an uninput TeX file. | Active-paper checks should ignore it; separate orphan lint is optional future work. |
| Comment parsing | Add bad citations/numbers/labels inside TeX comments. | Active-paper extractors should ignore comments. |

## Report Format

Use this shape for each probe:

````markdown
### P<N>: <short name>

Mutation:
- `<path>`: <field or TeX fragment changed>

Expected:
- <contract that should be enforced>

Commands:
```bash
<validator command>
<profile command>
```

Actual:
- <exit code and key diagnostic>

Classification:
- harness gap | case ledger debt | documentation friction |
  accepted regression fixture

Follow-up:
- <PR, issue, case cleanup, or no action>
````

## Interpreting Results

- Caught cleanly: keep as a regression idea or no-op.
- Caught with noisy duplicate diagnostics: group the diagnostics in the relevant
  validator only if noise hides the primary failure.
- Missed by a leaf check but caught by a broader check: decide whether the leaf
  check is advertised as an independent gate. If yes, strengthen it.
- Missed by every check: open a harness-fix PR in this repository or record a
  precise proposal.
- Fails on valid migrated paper: classify as false positive, then fix the
  validator here or narrow the case ledger.
