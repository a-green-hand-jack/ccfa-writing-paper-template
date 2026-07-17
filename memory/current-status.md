# Current Status

Objective: initialize evidence-first paper harness for `ccfa-paper-template`.

Next entrypoint: read `ANATOMY.md`, `state/ccfa.yaml`, `.agent/session-protocol.md`, then this file.

## Lane 3 (export/release) — arXivTeX-inspired hardening, 2026-07-17

Implements GitHub issues #10, #13, #12 (tracker #7), serially on one branch.

- **#10 arXiv export hardening**: `scripts/paper_harness_checks.py` `export_release()` now optionally
  latexpands `release/arxiv/main.tex` into a sibling `release/arxiv-flat/` (single-entry `main.tex` +
  `refs.bib` + style files + real figure/table assets, with `figures/srcs/`/`tables/srcs/` rewritten to
  flat `srcs/`). Tracked under `release/manifest.yaml`'s new `flatten` list (kept separate from
  `surfaces` so it never disturbs the existing byte-exact `paper/` <-> release surface freshness
  compare). Gracefully skipped (not failed) when `latexpand` is absent, and treated as a hard
  export-time failure when latexpand can't resolve an `\input` (a real hidden dependency). Added
  `scripts/check-latex.sh --compile-release [surface]` to compile the export directory itself (not
  `paper/`) — both the modular copy and, if present, `arxiv-flat/` — printing `UNVERIFIED` instead of a
  false pass when no TeX toolchain is present.
- **#13 LaTeX-safety policy + arXiv portability guardrail**: added `.agent/latex-policy.md` (harvested
  increment from arXivTeX's `AGENTS.md`, restated evidence-first; existing `.agent/*-policy.md` stubs
  were all identical placeholder boilerplate, so nothing there conflicted). Added
  `scripts/check-arxiv-portability.py` (folded into `check_release_package()`): flags non-standard
  fonts (`fontspec`/`\setmainfont`/...), absolute paths in `\input`/`\includegraphics`/`\graphicspath`/etc.,
  non-PDF/PNG/JPG figure assets, and project macros redefined inside a `.cls`/`.sty` file. Updated
  `.agent/checklists/latex.md`.
- **#12 Overleaf publish**: added `.github/workflows/overleaf-publish.yml` — `git subtree split
  --prefix=release/overleaf` pushed to an `overleaf` branch, gated by `check-release-package.py` +
  `check-release-freshness.py` + an explicit control-plane-leakage/symlink grep. Explicitly one-way
  (documented in `release/ANATOMY.md` and `.agent/release-policy.md`); no live badge added to this
  template's own `README.md` since its `paper/` is a placeholder skeleton, but a copy-paste "Open in
  Overleaf" badge snippet is documented for downstream projects. Verified locally with
  `git subtree split` against `release/overleaf`'s real git history (produced a clean tree, no leaked
  control-plane paths) — the actual GitHub Action push was not run since that requires the real remote.

Validators run and passing on this branch: `check-writing-harness.py`, `check-capability-parity.py`,
`check-anatomy-drift.py`, `export-tex-release.sh`, `check-release-package.py`,
`check-release-freshness.py`, `check-arxiv-portability.py`, `check-latex.sh --compile-release arxiv`,
`check-latex.sh --compile` (TeX Live 2026 available locally, so all of these were actually verified,
not just structurally checked).

Not verified: the `overleaf-publish.yml` GitHub Action itself was not executed against the real GitHub
remote (would require pushing/dispatching against the actual repo, which needs supervisor sign-off).
## Branch: fix/bridge-chassis-preflight-on-main — Bridge chassis adoption-readiness preflight (issue #6)

Note: this replays the original `bridge/chassis-writing-profile` preflight commit
onto current `main` (the old branch had diverged from main, pre-dating #14–#19).
Only the 9 chassis files from that commit are replayed; no unrelated work is
reverted.

Scope: Writing-side chassis/profile/pin/validator closure. This is an
**adoption-readiness preflight**, not upstream Bridge conformance — the Bridge
chassis-spec, protocol schemas, and golden fixtures are not vendored/pinned here
and Bridge issues #3/#6/#7 are open. See `DECISIONS.md` DEC-0003.

Changes:
- `state/ccfa.yaml`: declared `profile: writing` and `bridge.chassis_pin`.
- `state/bridge-chassis.yaml` (new): profile, explicit chassis/protocol semver
  pins (Writing-declared adoption targets), dual contract/schema versions,
  executable MAJOR baseline (`approved_major`), provisional compatibility matrix,
  MAJOR human gate, Writing-owned capability classification, and a
  governance-gated (candidate) writing->research promotion proposal. Framed
  explicitly as a preflight, not upstream conformance.
- `.agent/capabilities/registry.yaml`: added explicit `contract_version`,
  `schema_version`, `profile`, `ownership` (kept Writing-owned).
- `scripts/paper_harness_checks.py`: `check_bridge_chassis_preflight` and
  `check_capability_registry_contract`. Semver validation is fully anchored
  (rejects suffixed pins) and ranges require explicit comparator grammar. Pins
  are also proven to be *contained* in their declared range (`version_in_range`):
  `chassis.spec_version` in `chassis.compatible_range`, both `protocol.*` pins in
  `protocol.compatible_range`, and each matrix row's `pinned` in its own `range`.
  The provisional matrix must contain exactly one `chassis-spec` and one
  `version-pins` row (required + de-duplicated) before the canonical cross-checks
  run. The preflight independently catches registry drift (missing contract/schema
  version, wrong profile/ownership), asserts `capabilities.registry` equals the
  registry path, and runs an executable MAJOR gate. Proposed promotions must have
  a concrete non-placeholder `rfc` and concrete existing fixture path(s)
  (`not-vendored`/`TODO`/etc. are rejected). `check_capability_parity` also
  enforces registry contract/schema versioning and explicit parity/exemptions.
  Registered as `bridge_chassis_preflight` and wired into `check_writing_harness`.
- `scripts/check-bridge-chassis.py` (wrapper -> `bridge_chassis_preflight`);
  `scripts/ANATOMY.md` and `state/ANATOMY.md` documented the new surfaces.

Validator evidence (this branch, from repo root):
- `python3 -m py_compile scripts/paper_harness_checks.py scripts/check-bridge-chassis.py` -> exit 0.
- `python3 scripts/check-bridge-chassis.py` -> exit 0 (`OK bridge_chassis_preflight`; local self-consistency only).
- `python3 scripts/check-capability-parity.py` -> exit 0 (`OK capability_parity`).
- `python3 scripts/check-writing-harness.py` -> exit 0 (`OK writing_harness`).
- `git diff --check main...HEAD` -> clean.
- Negative checks (temp copies) confirm rejection of: suffixed semver
  (`1.0.0foo`), non-comparator range (`abc1`, `1.x`, `^1.0.0`), pin outside its
  range (`1.0.0` with `>=1.1.0 <2.0.0`) for chassis/protocol/matrix rows, missing
  or duplicate canonical matrix rows (`chassis-spec`, `version-pins`),
  `status: proposed` with placeholder fixtures (`not-vendored`), missing registry
  `contract_version`/`schema_version`, registry `profile`/`ownership` drift,
  `capabilities.registry` mismatch, matrix/pin contradiction, silent chassis
  MAJOR bump (`spec_version` 2.0.0 with `approved_major` 1), missing profile/pins,
  default-latest pins, contract mismatch, non-required parity without exemption,
  and any unclassified registry capability.

Remaining known limitations (out of scope here):
- #5/#4: real upstream Bridge conformance is not implemented. The Bridge
  chassis-spec, protocol schemas, and golden fixtures are not vendored; only
  Writing-owned pins and local self-consistency preflight exist. The `1.0.0`
  values and the compatibility matrix are provisional Writing-declared adoption
  targets and must be reconciled with the published Bridge chassis-spec once it
  exists. The promotion proposal stays a governance-gated candidate until a
  Bridge RFC and fixtures are in place.

## Case: arXiv 2604.01658 (CORAL) migration — 2026-07-18

Branch `case/arxiv-2604-01658` (worktree). Migration (authoring) lane only;
destructive stress probes out of scope.

- Normalized the COLM 2026 preprint TeX into `paper/` (sections, figures/srcs +
  wrappers, `style/colm2026_conference.sty|.bst`, `refs.bib`, `macros.tex`,
  `venue_preamble.tex`). Section `\input` order is ascending per anatomy; the
  fully-commented `07_limitations` slot renders nothing so fidelity is preserved.
- Populated the smallest honest control plane (claims, evidence, floats,
  figure/table/result indexes, notation, citation/reference ledgers).
- Fidelity gate `compare-original-pdf.sh 2604.01658`: 27 vs 27 pages, 0 compiled-only
  / 1 original-only line, within threshold — PASS.
- Migration debt recorded in
  `lab/harness-evals/20260718-arxiv-2604-01658-migration-baseline.md`
  (bulk numeric exception, citation fitness needs-review, ui subfigure convention
  gap, COLM venue-kit exemption).
