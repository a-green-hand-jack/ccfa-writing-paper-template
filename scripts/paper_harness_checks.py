#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_doc(path: str):
    text = (ROOT / path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except Exception:
        return json.loads(text)
    return yaml.safe_load(text)


def require(paths):
    missing = [p for p in paths if not (ROOT / p).exists()]
    if missing:
        for path in missing:
            print(f"ERROR missing {path}")
        return 1
    return 0


def check_capability_parity():
    code = require([".agent/capabilities/registry.yaml", ".claude/ANATOMY.md", ".agents/ANATOMY.md"])
    registry = load_doc(".agent/capabilities/registry.yaml")
    for cap in registry.get("capabilities", []):
        cid = cap["id"]
        code |= require([
            f".agent/capabilities/{cid}.yaml",
            cap["claude_adapter"]["skill"],
            cap["codex_adapter"]["workflow"],
        ])
    for role in registry.get("roles", []):
        code |= require([role["claude_agent"], role["codex_role"]])
    return code


def check_release_package():
    manifest = load_doc("release/manifest.yaml")
    forbidden_names = {".agent", ".claude", ".agents", "state", "lab", "memory", "human", "exemplars"}
    code = 0
    for surface in manifest.get("surfaces", []):
        root = ROOT / surface["path"]
        if not root.exists():
            print(f"ERROR missing release surface {surface['path']}")
            code = 1
            continue
        for path in root.rglob("*"):
            if any(part in forbidden_names for part in path.relative_to(root).parts):
                print(f"ERROR release surface leaks harness path: {path.relative_to(ROOT)}")
                code = 1
    return code


def check_worktrees():
    doc = load_doc("state/worktrees.yaml")
    ids = {item.get("id") for item in doc.get("worktrees", [])}
    code = 0
    for required in {"main", "dev"}:
        if required not in ids:
            print(f"ERROR missing worktree registry entry {required}")
            code = 1
    return code


def check_conference_template():
    ccfa = load_doc("state/ccfa.yaml")
    template = load_doc("state/conference-template.yaml")
    code = 0
    if template.get("venue") != ccfa.get("venue", {}).get("id"):
        print("ERROR conference template venue does not match state/ccfa.yaml")
        code = 1
    if template.get("year") != ccfa.get("venue", {}).get("year"):
        print("ERROR conference template year does not match state/ccfa.yaml")
        code = 1
    return code


def check_anatomy_drift():
    return require([
        "ANATOMY.md",
        "state/ANATOMY.md",
        "paper/ANATOMY.md",
        "lab/ANATOMY.md",
        "release/ANATOMY.md",
        "exemplars/ANATOMY.md",
        "human/ANATOMY.md",
        "memory/ANATOMY.md",
        "scripts/ANATOMY.md",
    ])


def check_claim_experiment_plan():
    claims = load_doc("state/claim-evidence-map.yaml").get("claims", [])
    plan = load_doc("lab/research/claim-experiment-plan.yaml").get("claims", [])
    plan_ids = {item.get("claim_id") for item in plan}
    code = 0
    for claim in claims:
        if claim.get("claim_strength") == "core" and claim.get("claim_id") not in plan_ids:
            print(f"ERROR core claim lacks experiment plan: {claim.get('claim_id')}")
            code = 1
    return code


def check_lab_lightweight():
    forbidden = ["pyproject.toml", "setup.py", "setup.cfg"]
    code = 0
    for name in forbidden:
        if (ROOT / "lab" / name).exists():
            print(f"ERROR lab must stay lightweight; found lab/{name}")
            code = 1
    return code


def check_writing_harness():
    code = 0
    code |= require(["state/ccfa.yaml", "state/claim-evidence-map.yaml", "state/numeric-registry.yaml", "lab/research/reference-ledger.yaml", "paper/main.tex", "release/manifest.yaml"])
    code |= check_anatomy_drift()
    code |= check_capability_parity()
    code |= check_conference_template()
    code |= check_worktrees()
    code |= check_release_package()
    code |= check_lab_lightweight()
    return code


def export_release():
    surfaces = ["release/arxiv", "release/overleaf", "release/github-tex"]
    allowed = ["main.tex", "macros.tex", "venue_preamble.tex", "refs.bib", "sections", "figures", "tables", "style", "generated", "supplementary"]
    for surface in surfaces:
        dest = ROOT / surface
        dest.mkdir(parents=True, exist_ok=True)
        for item in allowed:
            src = ROOT / "paper" / item
            if not src.exists():
                continue
            out = dest / item
            if src.is_dir():
                if out.exists():
                    shutil.rmtree(out)
                shutil.copytree(src, out)
            else:
                shutil.copy2(src, out)
    return check_release_package()


CHECKS = {
    "writing_harness": check_writing_harness,
    "anatomy_drift": check_anatomy_drift,
    "capability_parity": check_capability_parity,
    "claim_experiment_plan": check_claim_experiment_plan,
    "conference_template": check_conference_template,
    "lab_lightweight": check_lab_lightweight,
    "release_package": check_release_package,
    "worktrees": check_worktrees,
    "claim_evidence": lambda: require(["state/claim-evidence-map.yaml", "lab/research/evidence.yaml", "lab/research/evidence-gap-register.yaml"]),
    "result_status": lambda: require(["state/result-status.yaml", "lab/artifacts/result-index.yaml"]),
    "numeric_consistency": lambda: require(["state/numeric-registry.yaml", "state/numbers/numeric-index.yaml", "state/numbers/macros.yaml", "paper/generated/results-macros.tex"]),
    "reference_existence": lambda: require(["paper/refs.bib", "lab/research/reference-ledger.yaml"]),
    "citation_fitness": lambda: require(["lab/research/citation-ledger.yaml", "lab/research/related-work-map.yaml"]),
    "index_float_refs": lambda: require(["state/float-placement-map.yaml", "paper/figures/README.md", "paper/tables/README.md"]),
    "float_placement": lambda: require(["state/float-placement-map.yaml"]),
    "notation": lambda: require(["state/notation.yaml", "state/terminology.yaml"]),
    "anonymity": lambda: require(["state/ccfa.yaml", "release/manifest.yaml"]),
    "figures_tables": lambda: require(["lab/artifacts/figure-index.yaml", "lab/artifacts/table-index.yaml", "state/float-placement-map.yaml"]),
    "import_main_edits": lambda: require(["state/worktrees.yaml", "paper/ANATOMY.md"]),
    "export_release": export_release,
}


def run(name: str) -> int:
    if name not in CHECKS:
        print(f"ERROR unknown check {name}")
        return 2
    code = CHECKS[name]()
    if code == 0:
        print(f"OK {name}")
    return code


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: paper_harness_checks.py <check-name>", file=sys.stderr)
        return 2
    return run(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
