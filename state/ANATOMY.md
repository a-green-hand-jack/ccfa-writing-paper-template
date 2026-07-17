# State Anatomy

Live writing control plane. Read before drafting, reviewing, compiling, or exporting.

- `ccfa.yaml`: primary config surface. Declares `profile: writing` and the Bridge `chassis_pin`.
- `bridge-chassis.yaml`: Writing-side Bridge chassis adoption-readiness preflight (profile, chassis/protocol semver pins, executable MAJOR baseline, provisional compatibility matrix, MAJOR human gate). Writing-owned adoption surface, not upstream Bridge conformance — the Bridge chassis-spec, protocol schemas, and fixtures are not vendored here. Validated locally by `scripts/check-bridge-chassis.py`.
