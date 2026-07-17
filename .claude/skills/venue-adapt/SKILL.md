---
name: venue-adapt
description: adapt stable writing choices while forcing current-year official checks
---

# venue-adapt

Purpose: adapt stable writing choices while forcing current-year official checks.

Source capability: `.agent/capabilities/venue-adapt.yaml`. Read this file first and treat it as the contract for this run.

## Inputs

- `state/ccfa.yaml`
- `state/conference-template.yaml`
- `state/venue-profile.yaml`
- `paper/venue_preamble.tex`
- `paper/style/compat.sty`
- `scripts/export-venue-template.sh`

## Declared Outputs

- `state/venue-profile.yaml`
- `state/conference-template.yaml`
- `state/ccfa.yaml`
- `release/venue/`

## Validators

- `scripts/check-capability-parity.py`
- `scripts/check-conference-template.py`
- `scripts/check-anonymity.py`
- `scripts/check-latex.sh`

## Venue Conversion (compat.sty shim)

`paper/style/compat.sty` reimplements the `paper/style/ccfa-paper.sty` Class
API (`\parahead`, `\headbf`, `\figref`/`\tabref`/`\algref`/`\eqnref`,
`\tablestyle`, `\cmark`/`\xmark`, compact column types) on packages an
official venue class already loads, so `paper/sections/*.tex` compiles
unmodified under CVPR/ICCV/NeurIPS/etc.

`scripts/export-venue-template.sh --mode anonymous|camera-ready
[--raw-template <local-kit-path>]` copies `paper/` sources plus
`compat.sty` and the user-supplied official kit (never fetched from the
network) into `release/venue/<venue>-<year>-<mode>/`, generates a
`main.tex` bound to the official class, and independently compiles it.
It never edits `paper/`, `paper/refs.bib`, or the official kit files.
`release/venue/` is gitignored — regenerate it, do not hand-edit or
commit it. In anonymous mode, run `scripts/check-anonymity.py` after
export; it scans generated `*-anonymous/` venue exports for leaked
author names and emails in addition to the three release surfaces.

## Human Gates

- `current-year-official-rules`: required when Recording or changing current-year venue, anonymity, page-limit, or template rules. Record in `state/conference-template.yaml`.
- `scope-change`: required when A needed edit is outside allowed_paths, a forbidden_path must change, or facts are missing from repository sources. Record in `human/decisions/README.md`.

## Operating Steps

1. Read `.agent/capabilities/venue-adapt.yaml` and confirm the requested work matches this capability, its read_only_paths, allowed_paths, and forbidden_paths.
2. Read the declared inputs from the repository. Never infer paper facts from chat, memory, or prior conversation when the repo lacks evidence.
3. If a required input, evidence item, result, citation, venue rule, or human approval is missing, stop and record the blocker in `memory/current-status.md` or `human/inbox/README.md`.
4. Update declared outputs only. Do not edit capability specs, adapters, registry files, or unrelated paper state while executing this workflow.
5. Run the declared validators that match the touched outputs. Capture each command and whether it passed.
6. Finish only when the completion contract is met: changed files are declared outputs, validators passed or blockers are recorded, and the handoff names every remaining risk.

## Completion Contract

- Source capability reviewed: `.agent/capabilities/venue-adapt.yaml`
- Output contract: all successful edits are limited to the declared outputs above.
- Validator contract: run at least one declared validator and every validator relevant to touched outputs.
- Blocker contract: missing evidence, approvals, or path authority is recorded before handoff.
- Fact contract: never infer paper facts from chat; cite repository paths instead.

