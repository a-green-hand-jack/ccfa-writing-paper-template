# camera-ready-check

Purpose: gate final metadata, claims, numbers, references, and release files.

Source capability: `.agent/capabilities/camera-ready-check.yaml`. Read this file first and treat it as the contract for this run.

## Inputs

- `state/ccfa.yaml`
- `state/claim-evidence-map.yaml`
- `state/numeric-registry.yaml`
- `paper/main.tex`
- `release/manifest.yaml`

## Declared Outputs

- `release/reports/`
- `release/manifest.yaml`
- `memory/current-status.md`

## Validators

- `scripts/check-capability-parity.py`
- `scripts/check-writing-harness.py`
- `scripts/check-release-package.py`
- `scripts/check-release-freshness.py`

`check-writing-harness.py` runs `check-conference-template.py` internally,
which enforces the real-kit compile receipt gate (#17): once a populated
paper has a real `raw_template` configured, this run refuses to pass
unless a matching, fresh `realkit_receipts` entry exists for the current
venue/year/mode. See `.agents/workflows/venue-adapt.md` for how to
produce the receipt.

## Human Gates

- `final-submission`: required when Declaring the camera-ready or submission package ready to send. Record in `human/decisions/README.md`.
- `scope-change`: required when A needed edit is outside allowed_paths, a forbidden_path must change, or facts are missing from repository sources. Record in `human/decisions/README.md`.

## Operating Steps

1. Read `.agent/capabilities/camera-ready-check.yaml` and confirm the requested work matches this capability, its read_only_paths, allowed_paths, and forbidden_paths.
2. Read the declared inputs from the repository. Never infer paper facts from chat, memory, or prior conversation when the repo lacks evidence.
3. If a required input, evidence item, result, citation, venue rule, or human approval is missing, stop and record the blocker in `memory/current-status.md` or `human/inbox/README.md`.
4. Update declared outputs only. Do not edit capability specs, adapters, registry files, or unrelated paper state while executing this workflow.
5. Run the declared validators that match the touched outputs. Capture each command and whether it passed.
6. Finish only when the completion contract is met: changed files are declared outputs, validators passed or blockers are recorded, and the handoff names every remaining risk.

## Completion Contract

- Source capability reviewed: `.agent/capabilities/camera-ready-check.yaml`
- Output contract: all successful edits are limited to the declared outputs above.
- Validator contract: run at least one declared validator and every validator relevant to touched outputs.
- Blocker contract: missing evidence, approvals, or path authority is recorded before handoff.
- Fact contract: never infer paper facts from chat; cite repository paths instead.
