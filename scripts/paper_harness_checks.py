#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import csv
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(os.environ.get("PAPER_HARNESS_ROOT", Path(__file__).resolve().parents[1])).resolve()


INACTIVE_STATUSES = {"removed", "dropped", "superseded", "inactive", "archived"}
VERIFIED_STATUSES = {"verified", "complete", "accepted"}
PLANNED_STATUSES = {"planned", "todo", "draft", "placeholder"}
FLOAT_LABEL_PREFIXES = ("fig:", "figure:", "tab:", "table:")


def load_doc(path: str):
    text = (ROOT / path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except Exception:
        return json.loads(text)
    return yaml.safe_load(text) or {}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def error(message: str) -> int:
    print(f"ERROR {message}")
    return 1


def missingish(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return not stripped or stripped == "TODO" or stripped.startswith("TODO ")
    return False


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def strings(value):
    return [str(item) for item in as_list(value) if not missingish(item)]


def item_id(item, *fields):
    if not isinstance(item, dict):
        return None
    for field in fields:
        value = item.get(field)
        if not missingish(value):
            return str(value)
    return None


def is_active(item: dict) -> bool:
    status = str(item.get("status", "")).lower()
    return status not in INACTIVE_STATUSES


def is_verified(item: dict) -> bool:
    status = str(item.get("status", "")).lower()
    verification_state = str(item.get("verification_state", "")).lower()
    return status in VERIFIED_STATUSES or verification_state in VERIFIED_STATUSES


def is_planned(item: dict) -> bool:
    return str(item.get("status", "")).lower() in PLANNED_STATUSES


def doc_items(path: str, key: str):
    doc = load_doc(path)
    value = doc.get(key, [])
    if isinstance(value, list):
        return value
    return []


def collect_ids(items, fields, context: str, required: bool = True):
    ids = set()
    code = 0
    seen = {}
    for index, item in enumerate(items, start=1):
        ident = item_id(item, *fields)
        if not ident:
            if required:
                code |= error(f"{context}[{index}] missing id field {fields[0]}")
            continue
        if ident in seen:
            code |= error(f"{context} duplicate id {ident}")
        seen[ident] = index
        ids.add(ident)
    return code, ids


def path_exists_or_external(value) -> bool:
    if missingish(value):
        return True
    text = str(value)
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        return True
    if text.startswith("doi:") or text.startswith("arXiv:"):
        return True
    return (ROOT / text.split(":", 1)[0]).exists()


def read_csv_rows(path: str):
    target = ROOT / path
    if not target.exists():
        return []
    with target.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def paper_tex_files():
    paper = ROOT / "paper"
    if not paper.exists():
        return []
    return sorted(paper.rglob("*.tex"))


def read_paper_tex() -> str:
    chunks = []
    for path in paper_tex_files():
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    return "\n".join(chunks)


def extract_bibkeys(text: str) -> set[str]:
    return set(match.group(1).strip() for match in re.finditer(r"@\w+\s*\{\s*([^,\s]+)", text))


def extract_cite_keys(text: str) -> set[str]:
    keys = set()
    pattern = re.compile(r"\\(?:cite|citep|citet|citealp|parencite|textcite)(?:\[[^\]]*\])*\{([^}]*)\}")
    for match in pattern.finditer(text):
        for key in match.group(1).split(","):
            key = key.strip()
            if key:
                keys.add(key)
    return keys


def extract_macro_names(text: str) -> set[str]:
    names = set()
    pattern = re.compile(r"\\(?:newcommand|renewcommand|providecommand)\s*\{\\([^}]+)\}")
    for match in pattern.finditer(text):
        names.add("\\" + match.group(1))
    return names


def extract_labels(text: str) -> set[str]:
    return set(match.group(1).strip() for match in re.finditer(r"\\label\{([^}]+)\}", text))


def extract_refs(text: str) -> set[str]:
    refs = set()
    pattern = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref)\{([^}]+)\}")
    for match in pattern.finditer(text):
        for ref in match.group(1).split(","):
            ref = ref.strip()
            if ref:
                refs.add(ref)
    return refs


def float_label(label: str) -> bool:
    return label.startswith(FLOAT_LABEL_PREFIXES)


def require(paths):
    missing = [p for p in paths if not (ROOT / p).exists()]
    if missing:
        for path in missing:
            error(f"missing {path}")
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
        if cap.get("status") == "active" and not cap.get("outputs"):
            code |= error(f"active capability has no outputs: {cid}")
    for role in registry.get("roles", []):
        code |= require([role["claude_agent"], role["codex_role"]])
    return code


def check_release_package():
    ccfa = load_doc("state/ccfa.yaml")
    manifest = load_doc("release/manifest.yaml")
    forbidden_names = {".agent", ".claude", ".agents", "state", "lab", "memory", "human", "exemplars"}
    code = 0
    expected_surfaces = set(strings(ccfa.get("release", {}).get("surfaces", [])))
    manifest_surfaces = manifest.get("surfaces", [])
    seen = set()
    actual_surfaces = set()
    if expected_surfaces and not manifest_surfaces:
        code |= error("release manifest has no surfaces but state/ccfa.yaml declares release surfaces")
    for surface in manifest.get("surfaces", []):
        surface_id = surface.get("id")
        if not surface_id:
            code |= error("release surface missing id")
        elif surface_id in seen:
            code |= error(f"duplicate release surface id: {surface_id}")
        else:
            seen.add(surface_id)
            actual_surfaces.add(str(surface_id))
        for field in ["path", "source", "forbidden_paths"]:
            if field not in surface:
                code |= error(f"release surface {surface_id or '<missing>'} missing {field}")
        root = ROOT / surface["path"]
        if not root.exists():
            code |= error(f"missing release surface {surface['path']}")
            continue
        for path in root.rglob("*"):
            if any(part in forbidden_names for part in path.relative_to(root).parts):
                code |= error(f"release surface leaks harness path: {path.relative_to(ROOT)}")
    if expected_surfaces and actual_surfaces != expected_surfaces:
        code |= error(
            "release manifest surfaces do not match state/ccfa.yaml: "
            f"expected {sorted(expected_surfaces)}, found {sorted(actual_surfaces)}"
        )
    return code


def check_worktrees():
    doc = load_doc("state/worktrees.yaml")
    worktrees = doc.get("worktrees", [])
    ids = {item.get("id") for item in worktrees}
    code = 0
    for required in {"main", "dev"}:
        if required not in ids:
            code |= error(f"missing worktree registry entry {required}")
    _, seen = collect_ids(worktrees, ["id"], "state/worktrees.yaml worktrees")
    for item in worktrees:
        ident = item.get("id", "<missing>")
        for field in ["branch", "purpose", "visibility", "owned_paths", "forbidden_paths", "validators", "status"]:
            if field not in item:
                code |= error(f"worktree {ident} missing {field}")
        if item.get("id") == "main":
            forbidden = set(strings(item.get("forbidden_paths", [])))
            for required in [".agent/**", ".claude/**", ".agents/**", "state/**", "lab/**", "memory/**", "human/**"]:
                if required not in forbidden:
                    code |= error(f"main worktree forbidden_paths missing {required}")
        if item.get("id") == "dev" and item.get("visibility") != "private":
            code |= error("dev worktree must be private")
    return code


def check_conference_template():
    ccfa = load_doc("state/ccfa.yaml")
    template = load_doc("state/conference-template.yaml")
    code = 0
    if template.get("venue") != ccfa.get("venue", {}).get("id"):
        code |= error("conference template venue does not match state/ccfa.yaml")
    if template.get("year") != ccfa.get("venue", {}).get("year"):
        code |= error("conference template year does not match state/ccfa.yaml")
    if str(template.get("status", "")).lower() == "verified":
        for field in ["raw_template", "normalized_template", "delta", "hash", "source", "downloaded_at", "human_verified_at"]:
            if missingish(template.get(field)):
                code |= error(f"verified conference template missing {field}")
        for field in ["raw_template", "normalized_template", "delta"]:
            if not path_exists_or_external(template.get(field)):
                code |= error(f"verified conference template path/source not found: {field}={template.get(field)}")
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
        claim_id = item_id(claim, "claim_id", "id")
        if claim.get("claim_strength") == "core" and claim_id not in plan_ids:
            code |= error(f"core claim lacks experiment plan: {claim_id}")
    return code


def check_lab_lightweight():
    forbidden = ["pyproject.toml", "setup.py", "setup.cfg"]
    code = 0
    for name in forbidden:
        if (ROOT / "lab" / name).exists():
            code |= error(f"lab must stay lightweight; found lab/{name}")
    return code


def check_human_gate_assets():
    return require([
        ".agent/human-gates.md",
        ".agent/checklists/evidence-audit.md",
        ".agent/checklists/numeric-audit.md",
        ".agent/checklists/reference-audit.md",
        ".agent/checklists/release.md",
        ".agent/templates/claim-card.md",
        ".agent/templates/claim-experiment-card.md",
        ".agent/templates/evidence-card.md",
        ".agent/templates/numeric-card.md",
        ".agent/templates/reference-card.md",
        "human/decisions/README.md",
    ])


def check_claim_evidence():
    code = require([
        "state/claim-evidence-map.yaml",
        "state/evidence-matrix.csv",
        "lab/research/evidence.yaml",
        "lab/research/evidence-gap-register.yaml",
        "lab/research/claim-experiment-plan.yaml",
        "lab/research/expected-results.yaml",
        "lab/research/experiment-ledger.yaml",
    ])
    if code:
        return code

    claims = doc_items("state/claim-evidence-map.yaml", "claims")
    evidence = doc_items("lab/research/evidence.yaml", "evidence")
    gaps = doc_items("lab/research/evidence-gap-register.yaml", "gaps")
    plans = doc_items("lab/research/claim-experiment-plan.yaml", "claims")
    expected = doc_items("lab/research/expected-results.yaml", "expected_results")
    experiments = doc_items("lab/research/experiment-ledger.yaml", "experiments")

    claim_code, claim_ids = collect_ids(claims, ["claim_id", "id"], "claims", required=False)
    evidence_code, evidence_ids = collect_ids(evidence, ["evidence_id", "id"], "evidence", required=False)
    experiment_code, experiment_ids = collect_ids(experiments, ["experiment_id", "id"], "experiments", required=False)
    code |= claim_code | evidence_code | experiment_code

    gap_claim_ids = {item_id(item, "claim_id", "id") for item in gaps if item_id(item, "claim_id", "id")}
    plan_claim_ids = {item_id(item, "claim_id", "id") for item in plans if item_id(item, "claim_id", "id")}
    for plan in plans:
        plan_claim_id = item_id(plan, "claim_id", "id")
        if claim_ids and plan_claim_id not in claim_ids:
            code |= error(f"experiment plan references unknown claim: {plan_claim_id}")
        for experiment in as_list(plan.get("required_experiments")) + as_list(plan.get("optional_experiments")):
            if isinstance(experiment, dict):
                exp_id = item_id(experiment, "experiment_id", "id")
                if exp_id:
                    experiment_ids.add(exp_id)

    for claim in claims:
        claim_id = item_id(claim, "claim_id", "id")
        if not claim_id:
            continue
        refs = strings(claim.get("evidence_ids"))
        for evidence_id in refs:
            if evidence_id not in evidence_ids:
                code |= error(f"claim {claim_id} references unknown evidence {evidence_id}")
        strength = str(claim.get("claim_strength", claim.get("strength", ""))).lower()
        if is_active(claim) and strength in {"core", "strong"} and not refs and claim_id not in gap_claim_ids:
            code |= error(f"{strength} claim lacks evidence and no evidence gap is registered: {claim_id}")
        if strength == "core" and claim_id not in plan_claim_ids:
            code |= error(f"core claim lacks experiment plan: {claim_id}")

    for item in evidence:
        evidence_id = item_id(item, "evidence_id", "id")
        for claim_id in strings(item.get("claim_ids") or item.get("supports_claims")):
            if claim_id not in claim_ids:
                code |= error(f"evidence {evidence_id} references unknown claim {claim_id}")

    for gap in gaps:
        claim_id = item_id(gap, "claim_id", "id")
        if claim_id and claim_ids and claim_id not in claim_ids:
            code |= error(f"evidence gap references unknown claim: {claim_id}")

    for item in expected:
        claim_id = item_id(item, "claim_id")
        experiment_id = item_id(item, "experiment_id")
        if claim_id and claim_ids and claim_id not in claim_ids:
            code |= error(f"expected result references unknown claim: {claim_id}")
        if experiment_id and experiment_ids and experiment_id not in experiment_ids:
            code |= error(f"expected result references unknown experiment: {experiment_id}")

    allowed_relationships = {"supports", "contradicts", "qualifies", "motivates", "background"}
    for row_number, row in enumerate(read_csv_rows("state/evidence-matrix.csv"), start=2):
        claim_id = row.get("claim_id")
        evidence_id = row.get("evidence_id")
        relationship = row.get("relationship")
        if missingish(claim_id) or missingish(evidence_id):
            code |= error(f"evidence-matrix row {row_number} missing claim_id or evidence_id")
            continue
        if claim_id not in claim_ids:
            code |= error(f"evidence-matrix row {row_number} references unknown claim {claim_id}")
        if evidence_id not in evidence_ids:
            code |= error(f"evidence-matrix row {row_number} references unknown evidence {evidence_id}")
        if relationship and relationship not in allowed_relationships:
            code |= error(f"evidence-matrix row {row_number} has invalid relationship {relationship}")
    return code


def load_number_groups(registry: dict):
    numbers = []
    for group_path in strings(registry.get("groups", [])):
        if not (ROOT / group_path).exists():
            continue
        numbers.extend(doc_items(group_path, "numbers"))
    return numbers


def check_result_status():
    code = require(["state/result-status.yaml", "lab/artifacts/result-index.yaml", "state/claim-evidence-map.yaml"])
    if code:
        return code
    status_results = doc_items("state/result-status.yaml", "results")
    index_results = doc_items("lab/artifacts/result-index.yaml", "results")
    claims = doc_items("state/claim-evidence-map.yaml", "claims")

    code |= collect_ids(status_results, ["result_id", "id"], "state/result-status.yaml results", required=False)[0]
    index_code, index_ids = collect_ids(index_results, ["result_id", "id"], "lab/artifacts/result-index.yaml results", required=False)
    code |= index_code
    claim_ids = collect_ids(claims, ["claim_id", "id"], "claims", required=False)[1]

    for result in status_results:
        result_id = item_id(result, "result_id", "id")
        if is_verified(result) and result_id not in index_ids:
            code |= error(f"verified result missing from result-index: {result_id}")
    for result in index_results:
        result_id = item_id(result, "result_id", "id")
        if is_verified(result):
            if not (result.get("source") or result.get("artifacts") or result.get("evidence_ids")):
                code |= error(f"verified result lacks source/artifacts/evidence: {result_id}")
        for claim_id in strings(result.get("claims_supported")):
            if claim_ids and claim_id not in claim_ids:
                code |= error(f"result {result_id} supports unknown claim {claim_id}")
    return code


def check_numeric_consistency():
    code = require([
        "state/numeric-registry.yaml",
        "state/numbers/numeric-index.yaml",
        "state/numbers/macros.yaml",
        "state/result-status.yaml",
        "paper/generated/results-macros.tex",
        "lab/artifacts/result-index.yaml",
        "lab/research/evidence.yaml",
    ])
    if code:
        return code

    registry = load_doc("state/numeric-registry.yaml")
    index = load_doc("state/numbers/numeric-index.yaml")
    macro_doc = load_doc("state/numbers/macros.yaml")
    evidence_ids = collect_ids(doc_items("lab/research/evidence.yaml", "evidence"), ["evidence_id", "id"], "evidence", required=False)[1]
    numbers = []
    numbers.extend(as_list(registry.get("numbers")))
    numbers.extend(as_list(index.get("numbers")))
    numbers.extend(load_number_groups(registry))
    numbers = [item for item in numbers if isinstance(item, dict)]

    number_code, number_ids = collect_ids(numbers, ["numeric_id", "id"], "numbers", required=False)
    code |= number_code

    macros = macro_doc.get("macros", [])
    macro_map = {}
    if isinstance(macros, dict):
        macro_map.update({str(key): str(value) for key, value in macros.items() if not missingish(value)})
    elif isinstance(macros, list):
        for item in macros:
            if not isinstance(item, dict):
                continue
            numeric_id = item_id(item, "numeric_id", "id")
            macro = item.get("latex_macro") or item.get("macro")
            if numeric_id and not missingish(macro):
                macro_map[numeric_id] = str(macro)
    macro_text = (ROOT / "paper/generated/results-macros.tex").read_text(encoding="utf-8")
    generated_macros = extract_macro_names(macro_text)

    for numeric_id, macro in macro_map.items():
        if number_ids and numeric_id not in number_ids:
            code |= error(f"macro map references unknown numeric id {numeric_id}")
        normalized = macro if macro.startswith("\\") else "\\" + macro
        if normalized not in generated_macros:
            code |= error(f"macro map for {numeric_id} missing generated macro {normalized}")

    for number in numbers:
        numeric_id = item_id(number, "numeric_id", "id")
        for evidence_id in strings(number.get("evidence_ids")):
            if evidence_ids and evidence_id not in evidence_ids:
                code |= error(f"number {numeric_id} references unknown evidence {evidence_id}")
        display = number.get("display", {}) if isinstance(number.get("display"), dict) else {}
        macro = number.get("latex_macro") or display.get("latex_macro") or macro_map.get(numeric_id)
        if not missingish(macro):
            normalized = str(macro) if str(macro).startswith("\\") else "\\" + str(macro)
            if normalized not in generated_macros:
                code |= error(f"number {numeric_id} expects missing generated macro {normalized}")
        if is_verified(number) and not (number.get("source") or number.get("artifact_path") or number.get("run_id") or number.get("evidence_ids")):
            code |= error(f"verified number lacks source/artifact/evidence: {numeric_id}")
        derived = number.get("derived", {}) if isinstance(number.get("derived"), dict) else {}
        for dep_id in strings(derived.get("depends_on")):
            if number_ids and dep_id not in number_ids:
                code |= error(f"derived number {numeric_id} depends on unknown number {dep_id}")

    code |= check_result_status()
    return code


def check_reference_existence():
    code = require(["paper/refs.bib", "lab/research/reference-ledger.yaml", "lab/research/citation-ledger.yaml"])
    if code:
        return code
    bib_text = (ROOT / "paper/refs.bib").read_text(encoding="utf-8")
    bib_keys = extract_bibkeys(bib_text)
    references = doc_items("lab/research/reference-ledger.yaml", "references")
    citations = doc_items("lab/research/citation-ledger.yaml", "citations")
    code |= collect_ids(references, ["reference_id", "id", "bibkey"], "references", required=False)[0]
    code |= collect_ids(citations, ["citation_id", "id", "bibkey"], "citations", required=False)[0]

    reference_keys = set()
    for ref in references:
        key = item_id(ref, "bibkey")
        if key:
            reference_keys.add(key)
            if bib_keys and key not in bib_keys:
                code |= error(f"reference ledger bibkey missing from refs.bib: {key}")
    for citation in citations:
        citation_id = item_id(citation, "citation_id", "id", "bibkey")
        for key in strings(citation.get("bibkey") or citation.get("bibkeys")):
            if key not in bib_keys and key not in reference_keys:
                code |= error(f"citation {citation_id} references unknown bibkey {key}")

    paper_keys = extract_cite_keys(read_paper_tex())
    for key in paper_keys:
        if key not in bib_keys:
            code |= error(f"paper cites missing BibTeX key: {key}")
        if references and key not in reference_keys:
            code |= error(f"paper cites key not registered in reference-ledger: {key}")
    return code


def check_citation_fitness():
    code = require(["lab/research/citation-ledger.yaml", "lab/research/related-work-map.yaml"])
    if code:
        return code
    citations = doc_items("lab/research/citation-ledger.yaml", "citations")
    areas = doc_items("lab/research/related-work-map.yaml", "areas")
    for citation in citations:
        citation_id = item_id(citation, "citation_id", "id", "bibkey")
        if not citation.get("purpose") and citation.get("bibkey"):
            code |= error(f"citation {citation_id} missing purpose")
        if citation.get("fitness_status") in {"weak", "missing-better-source", "needs-review"} and not citation.get("notes"):
            code |= error(f"citation {citation_id} has weak fitness without notes")
    for area in areas:
        area_id = item_id(area, "area_id", "id")
        if area.get("required_citation_types") and not area.get("cited_keys") and not area.get("missing_candidates"):
            code |= error(f"related-work area {area_id} has requirements but no cited keys or missing candidates")
    return code


def check_float_placement():
    code = require(["state/float-placement-map.yaml", "lab/artifacts/figure-index.yaml", "lab/artifacts/table-index.yaml"])
    if code:
        return code
    floats = doc_items("state/float-placement-map.yaml", "floats")
    code |= collect_ids(floats, ["float_id", "id", "label"], "floats", required=False)[0]
    text = read_paper_tex()
    labels = extract_labels(text)
    refs = extract_refs(text)
    float_labels = {label for label in labels if float_label(label)}
    float_refs = {ref for ref in refs if float_label(ref)}
    mapped_labels = set()
    for item in floats:
        float_id = item_id(item, "float_id", "id", "label")
        label = item.get("label")
        if not missingish(label):
            mapped_labels.add(str(label))
        if is_active(item) and not is_planned(item):
            if missingish(label):
                code |= error(f"active float missing label: {float_id}")
            elif str(label) not in labels:
                code |= error(f"float map references label absent from paper tex: {label}")
            for field in ["asset_path", "tex_source", "caption_source"]:
                value = item.get(field)
                if not missingish(value) and not path_exists_or_external(value):
                    code |= error(f"float {float_id} has missing {field}: {value}")
        for claim_id in strings(item.get("nearby_claim_ids")):
            if missingish(claim_id):
                code |= error(f"float {float_id} has empty nearby claim id")
    for label in sorted(float_labels | float_refs):
        if label not in labels:
            code |= error(f"paper references undefined float label: {label}")
        if label not in mapped_labels:
            code |= error(f"paper float label is not registered in state/float-placement-map.yaml: {label}")
    return code


def check_figures_tables():
    code = require(["lab/artifacts/figure-index.yaml", "lab/artifacts/table-index.yaml", "state/float-placement-map.yaml"])
    if code:
        return code
    figures = doc_items("lab/artifacts/figure-index.yaml", "figures")
    tables = doc_items("lab/artifacts/table-index.yaml", "tables")
    code |= collect_ids(figures, ["figure_id", "id"], "figures", required=False)[0]
    code |= collect_ids(tables, ["table_id", "id"], "tables", required=False)[0]
    for item in figures + tables:
        ident = item_id(item, "figure_id", "table_id", "id")
        for field in ["path", "asset_path", "source"]:
            value = item.get(field)
            if not missingish(value) and not path_exists_or_external(value):
                code |= error(f"figure/table {ident} has missing {field}: {value}")
    code |= check_float_placement()
    return code


def check_notation():
    code = require(["state/notation.yaml", "state/terminology.yaml"])
    if code:
        return code
    symbols = doc_items("state/notation.yaml", "symbols")
    terms = doc_items("state/terminology.yaml", "terms")
    seen_symbols = {}
    for item in symbols:
        symbol = item.get("symbol") or item.get("latex")
        if missingish(symbol):
            code |= error("notation entry missing symbol/latex")
            continue
        symbol = str(symbol)
        meaning = str(item.get("meaning", "")).strip()
        if symbol in seen_symbols and seen_symbols[symbol] != meaning:
            code |= error(f"notation symbol has conflicting meanings: {symbol}")
        elif symbol in seen_symbols:
            code |= error(f"duplicate notation symbol: {symbol}")
        seen_symbols[symbol] = meaning
        first_defined = item.get("first_defined")
        if not missingish(first_defined) and not path_exists_or_external(first_defined):
            code |= error(f"notation symbol {symbol} has missing first_defined path: {first_defined}")

    seen_terms = {}
    for item in terms:
        term = item.get("term") or item.get("canonical") or item.get("name")
        if missingish(term):
            code |= error("terminology entry missing term/canonical/name")
            continue
        term = str(term).lower()
        definition = str(item.get("definition", item.get("meaning", ""))).strip()
        if term in seen_terms and seen_terms[term] != definition:
            code |= error(f"term has conflicting definitions: {term}")
        elif term in seen_terms:
            code |= error(f"duplicate term: {term}")
        seen_terms[term] = definition
        for alias in strings(item.get("aliases")):
            alias_key = alias.lower()
            if alias_key in seen_terms and seen_terms[alias_key] != definition:
                code |= error(f"term alias conflicts with existing term: {alias}")
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
    code |= check_human_gate_assets()
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
    "human_gate_assets": check_human_gate_assets,
    "claim_evidence": check_claim_evidence,
    "result_status": check_result_status,
    "numeric_consistency": check_numeric_consistency,
    "reference_existence": check_reference_existence,
    "citation_fitness": check_citation_fitness,
    "index_float_refs": lambda: require(["state/float-placement-map.yaml", "paper/figures/README.md", "paper/tables/README.md"]),
    "float_placement": check_float_placement,
    "notation": check_notation,
    "anonymity": lambda: require(["state/ccfa.yaml", "release/manifest.yaml"]),
    "figures_tables": check_figures_tables,
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
