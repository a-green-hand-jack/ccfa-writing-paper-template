# Decisions

## DEC-0001: Evidence-first writing control plane

Decision: register contribution, claims, evidence, numbers, references, floats, notation, and release policy before treating prose as paper-facing.

Rationale: paper errors usually come from untracked factual promotion, stale numbers, citation drift, and release leakage.

## DEC-0002: Separate harness and release surfaces

Decision: `paper/` is the editing surface, `release/` is a generated tex-only surface, and harness state remains private by default.
