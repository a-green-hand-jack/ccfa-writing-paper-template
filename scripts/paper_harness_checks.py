#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import csv
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(os.environ.get("PAPER_HARNESS_ROOT", Path(__file__).resolve().parents[1])).resolve()


INACTIVE_STATUSES = {"removed", "dropped", "superseded", "inactive", "archived"}
VERIFIED_STATUSES = {"verified", "complete", "accepted"}
PLANNED_STATUSES = {"planned", "todo", "draft", "placeholder"}
FLOAT_LABEL_PREFIXES = ("fig:", "figure:", "tab:", "table:")
REQUIRED_PAPER_SURFACE = [
    "paper/main.tex",
    "paper/macros.tex",
    "paper/venue_preamble.tex",
    "paper/refs.bib",
    "paper/sections/title.tex",
    "paper/sections/abstract.tex",
    "paper/sections/intro.tex",
    "paper/sections/related.tex",
    "paper/sections/method.tex",
    "paper/sections/exp.tex",
    "paper/sections/conclusion.tex",
    "paper/sections/limitations.tex",
    "paper/sections/acknowledgement.tex",
    "paper/sections/appendix.tex",
]
RELEASE_ITEMS = [
    "main.tex",
    "macros.tex",
    "venue_preamble.tex",
    "refs.bib",
    "sections",
    "figures",
    "tables",
    "style",
    "generated",
    "supplementary",
]
RELEASE_SYNC_STATUSES = {"synced", "fresh", "exported"}
CHECKSUM_ALGORITHM = "sha256"
FORBIDDEN_RELEASE_PARTS = {
    ".git",
    ".github",
    ".agent",
    ".claude",
    ".agents",
    "state",
    "lab",
    "memory",
    "human",
    "exemplars",
}
ALLOWABLE_RELEASE_METADATA_PARTS = {".github"}


def load_doc(path: str):
    text = (ROOT / path).read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except Exception:
        return json.loads(text)
    return yaml.safe_load(text) or {}


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def rel_posix(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


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


def paper_content_tex_files():
    files = []
    paper = ROOT / "paper"
    for path in paper_tex_files():
        rel_parts = path.relative_to(paper).parts
        if not rel_parts:
            continue
        if rel_parts[0] in {"generated", "style"}:
            continue
        if str(path.relative_to(ROOT)) in {"paper/macros.tex", "paper/venue_preamble.tex"}:
            continue
        files.append(path)
    return files


def read_paper_content_tex() -> str:
    chunks = []
    for path in paper_content_tex_files():
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


def adapter_text_path(path: str) -> Path:
    target = ROOT / path
    if target.is_dir():
        return target / "SKILL.md"
    return target


def compare_tree(source: Path, dest: Path) -> list[str]:
    mismatches = []
    if source.is_symlink():
        mismatches.append(f"{rel(source)} is a symlink")
    if dest.is_symlink():
        mismatches.append(f"{rel(dest)} is a symlink")
    if mismatches:
        return mismatches
    if not source.exists() and not dest.exists():
        return mismatches
    if source.exists() != dest.exists():
        mismatches.append(f"{rel(dest)} does not match {rel(source)}")
        return mismatches
    if source.is_file() or dest.is_file():
        if not source.is_file() or not dest.is_file():
            mismatches.append(f"{rel(dest)} type differs from {rel(source)}")
        elif source.read_bytes() != dest.read_bytes():
            mismatches.append(f"{rel(dest)} differs from {rel(source)}")
        return mismatches
    source_symlinks = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_symlink())
    dest_symlinks = sorted(path.relative_to(dest) for path in dest.rglob("*") if path.is_symlink())
    if source_symlinks:
        mismatches.append(f"{rel(source)} contains symlinks: {[str(item) for item in source_symlinks[:10]]}")
    if dest_symlinks:
        mismatches.append(f"{rel(dest)} contains symlinks: {[str(item) for item in dest_symlinks[:10]]}")
    source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file() and not path.is_symlink())
    dest_files = sorted(path.relative_to(dest) for path in dest.rglob("*") if path.is_file() and not path.is_symlink())
    if source_files != dest_files:
        missing = sorted(set(source_files) - set(dest_files))
        extra = sorted(set(dest_files) - set(source_files))
        if missing:
            mismatches.append(f"{rel(dest)} missing files from source: {[str(item) for item in missing[:10]]}")
        if extra:
            mismatches.append(f"{rel(dest)} has stale files not in source: {[str(item) for item in extra[:10]]}")
    for item in sorted(set(source_files) & set(dest_files)):
        if (source / item).read_bytes() != (dest / item).read_bytes():
            mismatches.append(f"{rel(dest / item)} differs from {rel(source / item)}")
    return mismatches


def release_surface_root(surface: dict) -> tuple[Path | None, str | None]:
    path_value = str(surface.get("path", "")).strip()
    if not path_value:
        return None, "missing path"
    path = Path(path_value)
    if path.is_absolute() or ".." in path.parts:
        return None, f"unsafe release surface path: {path_value}"
    if not path.parts or path.parts[0] != "release" or len(path.parts) < 2:
        return None, f"release surface path must be under release/<surface>: {path_value}"
    return ROOT / path, None


def allowed_release_parts(surface: dict) -> set[str]:
    allowed = set(strings(surface.get("allowed_hidden_paths", [])))
    allowed.update(strings(surface.get("allowed_metadata_paths", [])))
    normalized = {item.strip().strip("/") for item in allowed if item.strip()}
    return normalized & ALLOWABLE_RELEASE_METADATA_PARTS


def release_surface_readme(surface_id: str) -> str:
    return (
        f"# {surface_id} Release Surface\n\n"
        "Generated from `paper/` by `scripts/export-tex-release.sh`.\n"
        "Do not edit this directory as the primary paper source.\n"
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_release_checksums(root: Path) -> list[dict]:
    files = []
    if not root.exists() or root.is_symlink():
        return files
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink() or not path.is_file():
            continue
        files.append(
            {
                "relpath": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )
    return files


def scan_release_surface(surface_id: str, root: Path, surface: dict) -> int:
    code = 0
    if root.is_symlink():
        return error(f"release surface {surface_id} is a symlink: {rel_posix(root)}")
    if not root.exists():
        return code
    forbidden = FORBIDDEN_RELEASE_PARTS - allowed_release_parts(surface)
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel_parts = path.relative_to(root).parts
        if path.is_symlink():
            code |= error(f"release surface {surface_id} contains symlink: {path.relative_to(ROOT).as_posix()}")
        if any(part in forbidden for part in rel_parts):
            code |= error(f"release surface {surface_id} leaks harness or metadata path: {path.relative_to(ROOT).as_posix()}")
    return code


def validate_release_source_item(src: Path) -> list[str]:
    mismatches = []
    if not src.exists():
        return mismatches
    if src.is_symlink():
        mismatches.append(f"{src.relative_to(ROOT).as_posix()} is a symlink")
        return mismatches
    if src.is_dir():
        for path in sorted(src.rglob("*"), key=lambda item: item.relative_to(src).as_posix()):
            rel_parts = path.relative_to(src).parts
            if path.is_symlink():
                mismatches.append(f"{path.relative_to(ROOT).as_posix()} is a symlink")
            if any(part in FORBIDDEN_RELEASE_PARTS for part in rel_parts):
                mismatches.append(f"{path.relative_to(ROOT).as_posix()} would leak harness or metadata path")
    return mismatches


def parse_manifest_files(surface_id: str, surface: dict) -> tuple[int, dict[str, dict] | None]:
    files = surface.get("files")
    if not isinstance(files, list):
        return error(f"release surface {surface_id} missing manifest checksums"), None
    code = 0
    parsed: dict[str, dict] = {}
    relpaths = []
    for index, entry in enumerate(files, start=1):
        if not isinstance(entry, dict):
            code |= error(f"release surface {surface_id} checksum entry {index} is not a mapping")
            continue
        relpath = entry.get("relpath")
        sha256 = entry.get("sha256")
        size = entry.get("size")
        if not isinstance(relpath, str) or not relpath:
            code |= error(f"release surface {surface_id} checksum entry {index} missing relpath")
            continue
        relpath_path = Path(relpath)
        if relpath_path.is_absolute() or ".." in relpath_path.parts:
            code |= error(f"release surface {surface_id} checksum entry has unsafe relpath: {relpath}")
            continue
        if relpath in parsed:
            code |= error(f"release surface {surface_id} duplicate checksum relpath: {relpath}")
            continue
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            code |= error(f"release surface {surface_id} checksum entry {relpath} has invalid sha256")
        if not isinstance(size, int) or size < 0:
            code |= error(f"release surface {surface_id} checksum entry {relpath} has invalid size")
        parsed[relpath] = {"relpath": relpath, "sha256": sha256, "size": size}
        relpaths.append(relpath)
    if relpaths != sorted(relpaths):
        code |= error(f"release surface {surface_id} manifest checksum entries are not sorted")
    return code, parsed


def verify_surface_manifest_checksums(surface_id: str, root: Path, surface: dict) -> int:
    code, expected = parse_manifest_files(surface_id, surface)
    if expected is None:
        return code
    actual = {entry["relpath"]: entry for entry in collect_release_checksums(root)}
    expected_paths = set(expected)
    actual_paths = set(actual)
    missing = sorted(expected_paths - actual_paths)
    extra = sorted(actual_paths - expected_paths)
    if missing:
        code |= error(f"release surface {surface_id} missing files from manifest: {missing[:10]}")
    if extra:
        code |= error(f"release surface {surface_id} has files not in manifest: {extra[:10]}")
    for relpath in sorted(expected_paths & actual_paths):
        expected_entry = expected[relpath]
        actual_entry = actual[relpath]
        if expected_entry["size"] != actual_entry["size"]:
            code |= error(
                f"release surface {surface_id} checksum drift for {relpath}: "
                f"size {actual_entry['size']} != manifest {expected_entry['size']}"
            )
        if expected_entry["sha256"] != actual_entry["sha256"]:
            code |= error(f"release surface {surface_id} checksum drift for {relpath}: sha256 differs from manifest")
    return code


def git_value(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def source_revision() -> dict:
    commit = git_value("rev-parse", "--verify", "HEAD")
    tree = git_value("rev-parse", "--verify", "HEAD^{tree}")
    if not commit:
        return {}
    revision = {"treeish": "HEAD", "commit": commit}
    if tree:
        revision["tree"] = tree
    return revision


def check_capability_parity():
    code = require([".agent/capabilities/registry.yaml", ".claude/ANATOMY.md", ".agents/ANATOMY.md"])
    registry = load_doc(".agent/capabilities/registry.yaml")
    for cap in registry.get("capabilities", []):
        cid = cap["id"]
        source = f".agent/capabilities/{cid}.yaml"
        outputs = strings(cap.get("outputs"))
        validators = strings(cap.get("validators"))
        code |= require([
            source,
            cap["claude_adapter"]["skill"],
            cap["codex_adapter"]["workflow"],
        ])
        if cap.get("status") == "active" and not outputs:
            code |= error(f"active capability has no outputs: {cid}")
        if cap.get("status") == "active" and not validators:
            code |= error(f"active capability has no validators: {cid}")
        if (ROOT / source).exists():
            spec = load_doc(source)
            spec_outputs = strings(spec.get("outputs"))
            spec_validators = strings(spec.get("validators"))
            if spec.get("id") != cid:
                code |= error(f"capability spec id mismatch: {cid}")
            if cap.get("status") == "active" and not spec_outputs:
                code |= error(f"active capability spec has no outputs: {cid}")
            if cap.get("status") == "active" and not spec_validators:
                code |= error(f"active capability spec has no validators: {cid}")
            if outputs and spec_outputs and outputs != spec_outputs:
                code |= error(f"capability spec outputs differ from registry: {cid}")
            if validators and spec_validators and validators != spec_validators:
                code |= error(f"capability spec validators differ from registry: {cid}")
        declared_paths = outputs + validators
        for adapter in [cap["claude_adapter"]["skill"], cap["codex_adapter"]["workflow"]]:
            text_path = adapter_text_path(adapter)
            if not text_path.exists() or not text_path.is_file():
                code |= error(f"capability adapter text missing: {adapter}")
                continue
            text = text_path.read_text(encoding="utf-8")
            if source not in text:
                code |= error(f"capability adapter does not mention source capability {source}: {rel(text_path)}")
            if declared_paths and not any(path in text for path in declared_paths):
                code |= error(f"capability adapter does not mention a declared output or validator path: {rel(text_path)}")
    for role in registry.get("roles", []):
        code |= require([role["claude_agent"], role["codex_role"]])
    return code


def check_release_package():
    ccfa = load_doc("state/ccfa.yaml")
    manifest = load_doc("release/manifest.yaml")
    code = 0
    expected_surfaces = set(strings(ccfa.get("release", {}).get("surfaces", [])))
    manifest_surfaces = manifest.get("surfaces", [])
    seen = set()
    actual_surfaces = set()
    if expected_surfaces and not manifest_surfaces:
        code |= error("release manifest has no surfaces but state/ccfa.yaml declares release surfaces")
    for surface in manifest.get("surfaces", []):
        if not isinstance(surface, dict):
            code |= error("release surface entry must be a mapping")
            continue
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
        root, path_error = release_surface_root(surface)
        if path_error:
            code |= error(f"release surface {surface_id or '<missing>'} {path_error}")
            continue
        if not root.exists():
            code |= error(f"missing release surface {surface['path']}")
            continue
        code |= scan_release_surface(str(surface_id or "<missing>"), root, surface)
        if str(surface.get("status", "")).lower() in RELEASE_SYNC_STATUSES:
            code |= verify_surface_manifest_checksums(str(surface_id or "<missing>"), root, surface)
    if expected_surfaces and actual_surfaces != expected_surfaces:
        code |= error(
            "release manifest surfaces do not match state/ccfa.yaml: "
            f"expected {sorted(expected_surfaces)}, found {sorted(actual_surfaces)}"
        )
    code |= check_release_freshness()
    return code


def check_release_freshness():
    manifest = load_doc("release/manifest.yaml")
    code = 0
    for surface in manifest.get("surfaces", []):
        if not isinstance(surface, dict):
            code |= error("release surface entry must be a mapping")
            continue
        surface_id = surface.get("id", "<missing>")
        if str(surface.get("status", "")).lower() not in RELEASE_SYNC_STATUSES:
            continue
        root, path_error = release_surface_root(surface)
        if path_error:
            code |= error(f"release surface {surface_id} {path_error}")
            continue
        if not root.exists():
            code |= error(f"missing release surface {surface.get('path', '<missing>')}")
            continue
        code |= scan_release_surface(str(surface_id), root, surface)
        code |= verify_surface_manifest_checksums(str(surface_id), root, surface)
        for item in RELEASE_ITEMS:
            src = ROOT / "paper" / item
            dest = root / item
            for mismatch in compare_tree(src, dest):
                code |= error(f"release surface {surface_id} is stale: {mismatch}")
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


def paper_looks_populated() -> bool:
    content = read_paper_content_tex()
    if not content.strip():
        return False
    if "TODO" in content:
        return False
    return any([
        bool(extract_cite_keys(content)),
        bool(extract_labels(content)),
        bool(doc_items("state/claim-evidence-map.yaml", "claims")),
        bool(doc_items("lab/research/evidence.yaml", "evidence")),
        bool(doc_items("lab/research/reference-ledger.yaml", "references")),
    ])


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


def check_paper_surface():
    code = require(REQUIRED_PAPER_SURFACE)
    main = ROOT / "paper/main.tex"
    if not main.exists():
        return code
    text = main.read_text(encoding="utf-8")
    for section in [
        "title",
        "abstract",
        "intro",
        "related",
        "method",
        "exp",
        "conclusion",
        "limitations",
        "appendix",
    ]:
        if f"\\input{{sections/{section}}}" not in text:
            code |= error(f"paper/main.tex does not input paper/sections/{section}.tex")
    if "\\bibliography{refs}" not in text:
        code |= error("paper/main.tex must use paper/refs.bib via \\bibliography{refs}")
    return code


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
    content_text = read_paper_content_tex()
    evidence_ids = collect_ids(doc_items("lab/research/evidence.yaml", "evidence"), ["evidence_id", "id"], "evidence", required=False)[1]
    claims = doc_items("state/claim-evidence-map.yaml", "claims")
    numbers = []
    numbers.extend(as_list(registry.get("numbers")))
    numbers.extend(as_list(index.get("numbers")))
    numbers.extend(load_number_groups(registry))
    numbers = [item for item in numbers if isinstance(item, dict)]

    number_code, number_ids = collect_ids(numbers, ["numeric_id", "id"], "numbers", required=False)
    code |= number_code

    for claim in claims:
        claim_id = item_id(claim, "claim_id", "id")
        for numeric_id in strings(claim.get("numeric_ids")):
            if re.fullmatch(r"[A-Za-z]+\d+\s*-\s*[A-Za-z]?\d+", numeric_id):
                code |= error(f"claim {claim_id} uses unsupported numeric id range {numeric_id}; expand ranges explicitly")
            elif number_ids and numeric_id not in number_ids:
                code |= error(f"claim {claim_id} references unknown numeric id {numeric_id}")

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
            if is_verified(number) and normalized not in content_text:
                code |= error(f"verified number macro is not used in paper content: {numeric_id} {normalized}")
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
    citation_keys = set()
    for citation in citations:
        citation_keys.update(strings(citation.get("bibkey") or citation.get("bibkeys")))
    if paper_keys and not reference_keys:
        code |= error("paper has citations but reference-ledger is empty")
    if paper_keys and not citation_keys:
        code |= error("paper has citations but citation-ledger is empty")
    for key in paper_keys:
        if key not in bib_keys:
            code |= error(f"paper cites missing BibTeX key: {key}")
        if key not in reference_keys:
            code |= error(f"paper cites key not registered in reference-ledger: {key}")
        if key not in citation_keys:
            code |= error(f"paper cites key not registered in citation-ledger: {key}")
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


def check_anonymity():
    code = require(["state/ccfa.yaml", "release/manifest.yaml"])
    if code:
        return code
    ccfa = load_doc("state/ccfa.yaml")
    team = ccfa.get("team", {}) if isinstance(ccfa.get("team"), dict) else {}
    mode = str(team.get("anonymous_mode", "")).lower()
    if mode not in {"anonymous", "double-blind", "blind", "anonymized"}:
        return 0

    allowed_author_values = {"", "todo", "anonymous", "anonymous author", "anonymous authors"}
    scan_chunks = [read_paper_tex()]
    manifest = load_doc("release/manifest.yaml")
    for surface in manifest.get("surfaces", []):
        surface_root = ROOT / str(surface.get("path", ""))
        if surface_root.exists():
            for path in surface_root.rglob("*.tex"):
                try:
                    scan_chunks.append(path.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    continue
    scan_text = "\n".join(scan_chunks)
    lower_scan = scan_text.lower()

    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", scan_text, flags=re.I):
        code |= error("anonymous-mode paper exposes an email address in paper or release tex")

    authors = strings(team.get("authors"))
    if isinstance(team.get("authors"), str):
        authors = [part.strip() for part in team.get("authors", "").split(",") if part.strip()]
    for author in authors:
        normalized = author.lower().strip()
        if normalized in allowed_author_values or normalized.startswith("anonymous"):
            continue
        if normalized and normalized in lower_scan:
            code |= error(f"anonymous-mode paper exposes author name: {author}")

    for match in re.finditer(r"\\author\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", scan_text, flags=re.S):
        value = re.sub(r"\s+", " ", match.group(1)).strip()
        normalized = value.lower()
        if missingish(value) or normalized in allowed_author_values or "anonymous" in normalized:
            continue
        code |= error("anonymous-mode paper has non-anonymous \\author content")
    return code


def check_paper_populated():
    code = 0
    ccfa = load_doc("state/ccfa.yaml")
    paper = ccfa.get("paper", {}) if isinstance(ccfa.get("paper"), dict) else {}
    for field in ["slug", "title", "owner"]:
        if missingish(paper.get(field)):
            code |= error(f"populated paper missing state/ccfa.yaml paper.{field}")

    content = read_paper_content_tex()
    if "TODO" in content:
        code |= error("populated paper content still contains TODO placeholders")

    claims = doc_items("state/claim-evidence-map.yaml", "claims")
    evidence = doc_items("lab/research/evidence.yaml", "evidence")
    references = doc_items("lab/research/reference-ledger.yaml", "references")
    citations = doc_items("lab/research/citation-ledger.yaml", "citations")
    floats = doc_items("state/float-placement-map.yaml", "floats")
    results = doc_items("lab/artifacts/result-index.yaml", "results")
    conference = load_doc("state/conference-template.yaml")

    paper_keys = extract_cite_keys(read_paper_tex())
    labels = extract_labels(read_paper_tex())
    refs = extract_refs(read_paper_tex())
    float_labels = {label for label in labels | refs if float_label(label)}
    if paper_keys and not references:
        code |= error("populated paper with citations must register references")
    if paper_keys and not citations:
        code |= error("populated paper with citations must register citation ledger entries")
    if float_labels and not floats:
        code |= error("populated paper with floats must register float-placement map entries")
    if not claims:
        code |= error("populated paper must register at least one claim")
    if not evidence:
        code |= error("populated paper must register at least one evidence item")
    if claims and not results:
        code |= error("populated paper with claims must register result status/index entries")
    if ccfa.get("venue", {}).get("must_verify_current_year_rules"):
        verified = str(conference.get("status", "")).lower() == "verified"
        exempt = conference.get("verification_exemption") or conference.get("migration_exemption")
        if not verified and not exempt:
            code |= error("populated paper requires verified current-year venue template or explicit exemption")
    for item in evidence:
        evidence_id = item_id(item, "evidence_id", "id") or "<missing>"
        source = str(item.get("source", ""))
        if is_verified(item) and source.startswith("paper/") and not (item.get("artifact_path") or item.get("run_id") or item.get("external_source") or item.get("provenance")):
            code |= error(f"verified evidence should not point only to paper prose: {evidence_id}")

    code |= check_paper_surface()
    code |= check_claim_evidence()
    code |= check_numeric_consistency()
    code |= check_reference_existence()
    code |= check_citation_fitness()
    code |= check_figures_tables()
    code |= check_notation()
    code |= check_anonymity()
    code |= check_release_package()
    return code


def check_writing_harness():
    code = 0
    code |= require(["state/ccfa.yaml", "state/claim-evidence-map.yaml", "state/numeric-registry.yaml", "lab/research/reference-ledger.yaml", "paper/main.tex", "release/manifest.yaml"])
    code |= check_anatomy_drift()
    code |= check_capability_parity()
    code |= check_paper_surface()
    code |= check_conference_template()
    code |= check_worktrees()
    code |= check_release_package()
    code |= check_anonymity()
    if paper_looks_populated():
        code |= check_paper_populated()
    code |= check_lab_lightweight()
    code |= check_human_gate_assets()
    return code


def export_release():
    manifest_path = ROOT / "release/manifest.yaml"
    manifest = load_doc("release/manifest.yaml")
    if not isinstance(manifest, dict):
        manifest = {}
    surfaces = manifest.get("surfaces", [])
    if not surfaces:
        surfaces = [{"id": "arxiv", "path": "release/arxiv"}, {"id": "overleaf", "path": "release/overleaf"}, {"id": "github-tex", "path": "release/github-tex"}]
    code = 0
    normalized_surfaces = []
    for surface in surfaces:
        if not isinstance(surface, dict):
            code |= error("release surface entry must be a mapping")
            continue
        surface_id = str(surface.get("id", "unknown"))
        root, path_error = release_surface_root(surface)
        if path_error:
            code |= error(f"release surface {surface_id} {path_error}")
            continue
        if root.is_symlink():
            code |= error(f"release surface {surface_id} is a symlink: {rel_posix(root)}")
            continue
        normalized_surfaces.append(surface)
    for item in RELEASE_ITEMS:
        for mismatch in validate_release_source_item(ROOT / "paper" / item):
            code |= error(f"cannot export release source: {mismatch}")
    if code:
        return code
    surfaces = normalized_surfaces
    manifest["manifest_version"] = "release-manifest-v1"
    manifest["checksum_algorithm"] = CHECKSUM_ALGORITHM
    manifest["source_revision"] = source_revision()
    for surface in surfaces:
        surface_id = str(surface.get("id", "unknown"))
        dest, _ = release_surface_root(surface)
        assert dest is not None
        if dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "README.md").write_text(release_surface_readme(surface_id), encoding="utf-8")
        for item in RELEASE_ITEMS:
            src = ROOT / "paper" / item
            out = dest / item
            if not src.exists():
                continue
            if src.is_dir():
                shutil.copytree(src, out)
            else:
                shutil.copy2(src, out)
        code |= scan_release_surface(surface_id, dest, surface)
        surface["path"] = str(surface.get("path", f"release/{surface_id}"))
        surface["source"] = "paper/"
        surface["checksum_algorithm"] = CHECKSUM_ALGORITHM
        surface["files"] = collect_release_checksums(dest)
        surface["status"] = "synced"
    if code:
        return code
    manifest["surfaces"] = surfaces
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return check_release_package()


CHECKS = {
    "writing_harness": check_writing_harness,
    "paper_surface": check_paper_surface,
    "paper_populated": check_paper_populated,
    "anatomy_drift": check_anatomy_drift,
    "capability_parity": check_capability_parity,
    "claim_experiment_plan": check_claim_experiment_plan,
    "conference_template": check_conference_template,
    "lab_lightweight": check_lab_lightweight,
    "release_package": check_release_package,
    "release_freshness": check_release_freshness,
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
    "anonymity": check_anonymity,
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
