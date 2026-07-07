---
name: contribution-lock
description: record and gate accepted contributions
---

# contribution-lock

Purpose: record and gate accepted contributions.

Source capability: `.agent/capabilities/contribution-lock.yaml`. Read this file first and treat it as the contract for this run.

## Inputs

- `state/ccfa.yaml`
- `state/confirmed-contribution.md`
- `state/contribution-map.yaml`
- `human/decisions/README.md`

## Declared Outputs

- `state/confirmed-contribution.md`
- `state/contribution-map.yaml`
- `DECISIONS.md`

## Validators

- `scripts/check-capability-parity.py`
- `scripts/check-writing-harness.py`

## Human Gates

- `confirm-contribution`: required when Marking a contribution as accepted or paper-facing. Record in `state/confirmed-contribution.md`.
- `scope-change`: required when A needed edit is outside allowed_paths, a forbidden_path must change, or facts are missing from repository sources. Record in `human/decisions/README.md`.

## Operating Steps

1. Read `.agent/capabilities/contribution-lock.yaml` and confirm the requested work matches this capability, its read_only_paths, allowed_paths, and forbidden_paths.
2. Read the declared inputs from the repository. Never infer paper facts from chat, memory, or prior conversation when the repo lacks evidence.
3. If a required input, evidence item, result, citation, venue rule, or human approval is missing, stop and record the blocker in `memory/current-status.md` or `human/inbox/README.md`.
4. Update declared outputs only. Do not edit capability specs, adapters, registry files, or unrelated paper state while executing this workflow.
5. Run the declared validators that match the touched outputs. Capture each command and whether it passed.
6. Finish only when the completion contract is met: changed files are declared outputs, validators passed or blockers are recorded, and the handoff names every remaining risk.

## Completion Contract

- Source capability reviewed: `.agent/capabilities/contribution-lock.yaml`
- Output contract: all successful edits are limited to the declared outputs above.
- Validator contract: run at least one declared validator and every validator relevant to touched outputs.
- Blocker contract: missing evidence, approvals, or path authority is recorded before handoff.
- Fact contract: never infer paper facts from chat; cite repository paths instead.

