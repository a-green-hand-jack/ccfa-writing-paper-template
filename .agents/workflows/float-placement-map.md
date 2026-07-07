# float-placement-map

Purpose: track figure and table mentions, claims, and compiled placement.

Source capability: `.agent/capabilities/float-placement-map.yaml`. Read this file first and treat it as the contract for this run.

## Inputs

- `paper/sections/`
- `paper/figures/`
- `paper/tables/`
- `lab/artifacts/figure-index.yaml`
- `lab/artifacts/table-index.yaml`

## Declared Outputs

- `state/float-placement-map.yaml`
- `lab/artifacts/figure-index.yaml`
- `lab/artifacts/table-index.yaml`

## Validators

- `scripts/check-capability-parity.py`
- `scripts/index-float-refs.py`
- `scripts/check-float-placement.py`
- `scripts/check-figures-tables.py`

## Human Gates

- `accept-float`: required when Adding a figure or table that carries a claim, result, or reviewer-facing artifact. Record in `human/decisions/README.md`.
- `scope-change`: required when A needed edit is outside allowed_paths, a forbidden_path must change, or facts are missing from repository sources. Record in `human/decisions/README.md`.

## Operating Steps

1. Read `.agent/capabilities/float-placement-map.yaml` and confirm the requested work matches this capability, its read_only_paths, allowed_paths, and forbidden_paths.
2. Read the declared inputs from the repository. Never infer paper facts from chat, memory, or prior conversation when the repo lacks evidence.
3. If a required input, evidence item, result, citation, venue rule, or human approval is missing, stop and record the blocker in `memory/current-status.md` or `human/inbox/README.md`.
4. Update declared outputs only. Do not edit capability specs, adapters, registry files, or unrelated paper state while executing this workflow.
5. Run the declared validators that match the touched outputs. Capture each command and whether it passed.
6. Finish only when the completion contract is met: changed files are declared outputs, validators passed or blockers are recorded, and the handoff names every remaining risk.

## Completion Contract

- Source capability reviewed: `.agent/capabilities/float-placement-map.yaml`
- Output contract: all successful edits are limited to the declared outputs above.
- Validator contract: run at least one declared validator and every validator relevant to touched outputs.
- Blocker contract: missing evidence, approvals, or path authority is recorded before handoff.
- Fact contract: never infer paper facts from chat; cite repository paths instead.
