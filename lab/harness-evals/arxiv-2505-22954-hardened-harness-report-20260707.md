# Hardened Harness Stress Test: arXiv 2505.22954

Date: 2026-07-07

Case branch: `case/arxiv-2505-22954-harness-1bcbd95`

Case baseline: `origin/case/arxiv-2505-22954` at `9f7a6d4`

Template sync source: `/home/user/Projects/research-project-harness` at `1bcbd953533d0763435bb695d7b13ef68f35fd7f` (`Harden float provenance and float binding`)

Template sync applied through template repo `origin/main` commit `fadadc2` (`Sync paper template from harness 1bcbd95`), merged into the case branch as `c86e624`.

## Final Check Matrix

All required checks passed after the case fixes below.

| Check | Final result |
| --- | --- |
| `PYTHONPATH=/home/user/Projects/research-project-harness/src PYTHONDONTWRITEBYTECODE=1 python3 -m research_project_harness validate --profile paper .` | pass, `OK: paper harness valid` |
| `python3 scripts/check-writing-harness.py` | pass, `OK writing_harness` |
| `python3 scripts/check-paper-surface.py` | pass, `OK paper_surface` |
| `python3 scripts/check-paper-populated.py` | pass, `OK paper_populated` |
| `python3 scripts/check-capability-parity.py` | pass, `OK capability_parity` |
| `python3 scripts/check-claim-evidence.py` | pass, `OK claim_evidence` |
| `python3 scripts/check-numeric-consistency.py` | pass, `OK numeric_consistency` |
| `python3 scripts/check-reference-existence.py` | pass, `OK reference_existence` |
| `python3 scripts/check-citation-fitness.py` | pass, `OK citation_fitness` |
| `python3 scripts/check-float-placement.py` | pass, `OK float_placement` |
| `python3 scripts/check-figures-tables.py` | pass, `OK figures_tables` |
| `python3 scripts/check-notation.py` | pass, `OK notation` |
| `bash scripts/export-tex-release.sh` | pass, `OK export_release` |
| `python3 scripts/check-release-package.py` | pass, `OK release_package` |
| `python3 scripts/check-release-freshness.py` | pass, `OK release_freshness` |
| `bash scripts/check-latex.sh --compile` | pass, `OK latex-compile` |
| `latexmk` in `release/arxiv` | pass |
| `latexmk` in `release/overleaf` | pass |
| `latexmk` in `release/github-tex` | pass |

## Initial Failures After Sync

- `check-citation-fitness.py` failed on every migrated citation because the ledger used `fitness_status: accepted`, which is no longer an allowed value, and entries had no context/locator.
- `check-numeric-consistency.py` reported 300 unregistered numeric literals. The largest sources were raw SWE-bench task-id lists (`paper/supplementary/swebench_tasks/*.tex`), supplementary Git diffs, appendix result prose/tables, and LaTeX layout dimensions such as `0.48\textwidth`.
- `check-figures-tables.py` failed three verified tables: `tab-DGM-greedy`, `tab-code_editing`, and `tab-fm-hyperparam` had no `numeric_ids` or `result_ids`.
- `check-writing-harness.py` initially failed loudly because the hardened release manifest from the template sync no longer matched the real case release surfaces. `bash scripts/export-tex-release.sh` fixed the release surface and manifest drift.

## Fixes Made

- Refreshed release artifacts and `release/manifest.yaml` with the hardened exporter.
- Updated `lab/research/citation-ledger.yaml`: changed migrated citations from `accepted` to `needs-review`, and added a provenance-preserving context and note to avoid claiming manual citation fitness was audited.
- Added appendix/experiment evidence records in `lab/research/evidence.yaml` and reciprocal rows in `state/evidence-matrix.csv`.
- Added verified reported-number entries in `state/numbers/groups/appendix.yaml` for appendix and experiment-section metrics that came directly from the migrated arXiv source.
- Added targeted numeric exceptions in `state/numbers/exceptions.yaml` for non-claim numerics: LaTeX layout dimensions, model/date metadata, raw SWE-bench task IDs, Git diff modes/hashes/hunk ranges, and code constants inside supplementary diff listings.
- Tightened the model/date numeric exception during main-agent review so it matches only model-version/date literals. The first draft used a context-wide pattern that could also excuse registered result/metadata literals on the same line. Upstream harness `e7ef260` now defaults exceptions to literal matching and treats verified non-macro numbers as registered literals, so the case no longer needs a registered-nonmacro exception.
- Added result ledger entries in `lab/artifacts/result-index.yaml` and `state/result-status.yaml`, then bound the three previously failing tables in `lab/artifacts/table-index.yaml`.
- Added this report under `lab/harness-evals/` and updated `lab/ANATOMY.md`.

## What Worked Well

- The template sync path worked cleanly: merging `origin/main` brought in the hardened validator and manifest logic without modifying the upstream harness repo.
- Release-surface checks caught a real post-sync gap immediately. The case had valid TeX surfaces, but the hardened manifest needed to be regenerated after the merge.
- Citation and table checks caught real missing contract data in the migrated case ledgers.
- Reference existence, float placement, notation, capability parity, and LaTeX compilation were stable on the real arXiv source.

## Friction And Design Findings

- Citation migration needs a first-class bulk status. The case had 100+ original-author citations from the arXiv source; requiring per-citation context is reasonable for new writing, but noisy for a migration audit. The current checker can be satisfied with a generic context on every entry, which is formally compliant but low signal.
- Numeric scanning is too broad for supplementary source packages. It scans raw task-id lists and Git patch listings as if every number were a paper claim. That is useful for catching hidden numbers, but the noise is severe on real arXiv source bundles.
- Numeric exception path scoping remains useful. Upstream harness `e7ef260` added `path_pattern`, but this case still uses literal-only exceptions for task ids and Git diff fragments until those paths are normalized.
- Context-wide exception matching used to be risky: a model-version exception could accidentally match the whole sentence and excuse unrelated result literals in the same context. Upstream harness `e7ef260` fixed the default by requiring explicit `match_scope` for context matching.
- Verified non-macro numbers were a design bug in the first hardened checker: the case registered reported appendix numbers with evidence and provenance, but still needed an exception. Upstream harness `e7ef260` now treats verified non-macro ledger values as registered literals.
- Table binding is valuable for quantitative tables, but too blunt for configuration tables such as `tab:fm-hyperparam`. Binding a result ID made the check pass, but `explicitly_qualitative` or a `kind: configuration` escape hatch would be more honest.

## Upstream Improvement Ideas

- Add `migration_source: arxiv` or `bulk_import_status: needs-review` support for citation ledgers, with a separate audit target for citations that actually need sentence-level review.
- Convert broad task-id and Git-diff numeric exceptions to `path_pattern`-scoped exceptions.
- Continue using literal-first exception matching and explicit `match_scope` for any future context exception.
- Keep verified non-macro numeric ledger entries in the registry rather than duplicating them in exceptions.
- Classify tables as `quantitative`, `qualitative`, or `configuration` so table binding expectations are explicit.
- Collapse repeated release-manifest errors by surface/file class when `check-writing-harness.py` aggregates checks.
