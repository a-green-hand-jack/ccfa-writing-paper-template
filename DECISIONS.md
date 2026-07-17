# Decisions

## DEC-0001: Evidence-first writing control plane

Decision: register contribution, claims, evidence, numbers, references, floats, notation, and release policy before treating prose as paper-facing.

Rationale: paper errors usually come from untracked factual promotion, stale numbers, citation drift, and release leakage.

## DEC-0002: Separate harness and release surfaces

Decision: `paper/` is the editing surface, `release/` is a generated tex-only surface, and harness state remains private by default.

## DEC-0003: Writing-side Bridge chassis adoption-readiness preflight (issue #6)

Decision: declare `profile: writing` and record Writing-side adoption pins for the `research-writing-bridge` chassis/protocol contracts in `state/bridge-chassis.yaml` (with `state/ccfa.yaml` as the profile/pin pointer). This is a Writing-side adoption-readiness preflight, **not** upstream Bridge conformance: the Bridge chassis-spec, protocol schemas, and golden fixtures are not vendored or pinned here, and Bridge issues #3/#6/#7 remain open. Pins must be fully explicit semver (suffix garbage and default-latest/floating pins are rejected) and ranges must use explicit comparator grammar. The capability registry carries explicit `contract_version`/`schema_version`, stays `profile: writing` / `ownership: writing-owned`, and every registered capability is classified as profile-specific so Writing's paper capabilities are never demanded as generic Bridge chassis. The compatibility matrix is provisional and its canonical rows are cross-checked against the local pins. `scripts/check-bridge-chassis.py` enforces this local self-consistency; the chassis MAJOR gate is executable (a `spec_version` MAJOR bump fails unless `approved_major` is edited in tandem, with the decision recorded at `human/decisions/README.md`).

Rationale: Writing prepares to consume the Bridge chassis-spec without silently drifting from Research, keeps its own implementation and paper-specific capabilities, and offers only the declarative-registry+parity pattern upstream as a governance-gated candidate. Passing the preflight means the Writing-side adoption surface is internally consistent, not that Writing has been validated against a published Bridge contract.
