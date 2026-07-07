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
SUPPORT_RELATIONSHIPS = {"supports", "qualifies"}
CONTRADICT_RELATIONSHIPS = {"contradicts"}
ALLOWED_EVIDENCE_RELATIONSHIPS = SUPPORT_RELATIONSHIPS | CONTRADICT_RELATIONSHIPS | {
    "motivates",
    "background",
}
CLAIM_STATEMENT_FIELDS = ("statement", "text", "claim", "summary")
EVIDENCE_SUPPORT_FIELDS = ("claim_ids", "supports_claims", "supported_claims", "claims_supported")
EVIDENCE_PROVENANCE_FIELDS = (
    "source",
    "provenance",
    "artifact",
    "artifact_path",
    "artifacts",
    "external_source",
    "run_id",
    "url",
    "uri",
    "doi",
)
EVIDENCE_QUALITY_FIELDS = (
    "strength",
    "evidence_strength",
    "support_strength",
    "fitness",
    "evidence_fitness",
    "fitness_status",
    "source_status",
    "status",
    "verification_state",
)
INSUFFICIENT_EVIDENCE_QUALITY = {
    "bare",
    "draft",
    "fail",
    "failed",
    "insufficient",
    "low",
    "missing",
    "placeholder",
    "planned",
    "todo",
    "unknown",
    "unverified",
    "unsupported",
    "weak",
}
CITATION_FITNESS_STATUSES = {"strong", "adequate", "weak", "missing-better-source", "needs-review"}
WEAK_CITATION_FITNESS_STATUSES = {"weak", "missing-better-source", "needs-review"}
CITATION_CONTEXT_FIELDS = ("context", "locator", "section", "quote")
CITATION_BULK_CONTEXT_THRESHOLD = 3
CITATION_BULK_IMPORT_REQUIRED_FIELDS = ("bulk_import_status", "migration_source", "fitness_review_status")
FLOAT_LABEL_PREFIXES = ("fig:", "figure:", "tab:", "table:")
NUMERIC_LITERAL_RE = re.compile(
    r"(?<![A-Za-z0-9_\\])"
    r"[-+]?"
    r"(?:"
    r"\d+(?:\.\d+)?\s*(?:\\%|%)"
    r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"
    r"|\d+\.\d+(?:[eE][-+]?\d+)?"
    r"|\d+(?:\.\d+)?[eE][-+]?\d+"
    r"|\d{4,}"
    r")"
    r"(?![A-Za-z0-9_])"
)
MASKED_NUMERIC_CONTEXT_COMMANDS = (
    "cite",
    "citep",
    "citet",
    "citealp",
    "parencite",
    "textcite",
    "ref",
    "eqref",
    "autoref",
    "cref",
    "Cref",
    "label",
    "url",
    "href",
    "include",
    "input",
    "includegraphics",
    "bibliography",
    "bibliographystyle",
    "vspace",
    "hspace",
    "setlength",
)
PROVENANCE_FIELDS = ("source", "generated_by", "artifact_path", "input_data", "checksum", "external_source")
PROVENANCE_PATH_FIELDS = ("source", "generated_by", "artifact_path", "input_data", "external_source")
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


def key_strings(value):
    keys = []
    for item in as_list(value):
        if missingish(item):
            continue
        if isinstance(item, str):
            keys.extend(part.strip() for part in item.split(",") if not missingish(part))
        else:
            keys.append(str(item))
    return keys


def meaningful(value) -> bool:
    if isinstance(value, dict):
        return any(meaningful(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(meaningful(item) for item in value)
    return not missingish(value)


def has_any_field(item: dict, fields) -> bool:
    return any(meaningful(item.get(field)) for field in fields)


def citation_bibkeys(citation: dict) -> list[str]:
    keys = []
    for field in ["bibkey", "bibkeys"]:
        keys.extend(key_strings(citation.get(field)))
    return list(dict.fromkeys(keys))


def citation_context_signature(citation: dict) -> tuple[str, ...]:
    values = []
    for field in CITATION_CONTEXT_FIELDS:
        value = citation.get(field)
        if missingish(value):
            values.append("")
        elif isinstance(value, (dict, list, tuple)):
            values.append(json.dumps(value, sort_keys=True))
        else:
            values.append(re.sub(r"\s+", " ", str(value).strip()).lower())
    return tuple(values)


def check_citation_bulk_import_state(citation_ledger: dict, citations: list[dict]) -> int:
    repeated_contexts: dict[tuple[str, ...], list[str]] = {}
    for citation in citations:
        if not isinstance(citation, dict) or not active_now(citation):
            continue
        fitness_status = str(citation.get("fitness_status", "")).strip().lower()
        if fitness_status not in WEAK_CITATION_FITNESS_STATUSES:
            continue
        signature = citation_context_signature(citation)
        if not any(signature):
            continue
        citation_id = item_id(citation, "citation_id", "id", "bibkey")
        repeated_contexts.setdefault(signature, []).append(citation_id)

    bulk_groups = [ids for ids in repeated_contexts.values() if len(ids) >= CITATION_BULK_CONTEXT_THRESHOLD]
    if not bulk_groups:
        return 0
    missing_fields = [field for field in CITATION_BULK_IMPORT_REQUIRED_FIELDS if not meaningful(citation_ledger.get(field))]
    if not missing_fields:
        return 0
    sample = ", ".join(bulk_groups[0][:3])
    missing = ", ".join(missing_fields)
    required = ", ".join(CITATION_BULK_IMPORT_REQUIRED_FIELDS)
    return error(
        "citation-ledger has repeated weak citation contexts "
        f"({sample}); add top-level bulk migration state fields: {missing} "
        f"(required: {required})"
    )


def reference_bibkeys(ref: dict) -> list[str]:
    keys = []
    for field in ["bibkey", "bibkeys"]:
        keys.extend(key_strings(ref.get(field)))
    return list(dict.fromkeys(keys))


def active_now(item: dict) -> bool:
    return is_active(item) and not is_planned(item)


def missing_candidate_notes(area: dict) -> bool:
    if has_any_field(area, ["notes", "missing_notes", "coverage_notes"]):
        return True
    candidates = as_list(area.get("missing_candidates"))
    if not candidates:
        return False
    for candidate in candidates:
        if not isinstance(candidate, dict) or not has_any_field(candidate, ["notes", "reason", "rationale"]):
            return False
    return True


def leaf_values(value):
    if isinstance(value, dict):
        values = []
        for child in value.values():
            values.extend(leaf_values(child))
        return values
    if isinstance(value, (list, tuple, set)):
        values = []
        for child in value:
            values.extend(leaf_values(child))
        return values
    return [value]


def has_value(value) -> bool:
    return any(not missingish(item) for item in leaf_values(value))


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


def has_meaningful_value(value) -> bool:
    if missingish(value):
        return False
    if isinstance(value, dict):
        return any(has_meaningful_value(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(has_meaningful_value(item) for item in value)
    return True


def normalized_text(value) -> str:
    return str(value).strip().lower()


def claim_strength(claim: dict) -> str:
    return normalized_text(claim.get("claim_strength", claim.get("strength", "")))


def has_claim_statement(claim: dict) -> bool:
    return any(has_meaningful_value(claim.get(field)) for field in CLAIM_STATEMENT_FIELDS)


def evidence_support_claim_ids(evidence_item: dict) -> list[str]:
    claim_ids = []
    for field in EVIDENCE_SUPPORT_FIELDS:
        claim_ids.extend(strings(evidence_item.get(field)))
    return claim_ids


def has_evidence_provenance(evidence_item: dict) -> bool:
    return any(has_meaningful_value(evidence_item.get(field)) for field in EVIDENCE_PROVENANCE_FIELDS)


def evidence_quality_values(evidence_item: dict) -> list[str]:
    values = []
    for field in EVIDENCE_QUALITY_FIELDS:
        value = evidence_item.get(field)
        if has_meaningful_value(value):
            values.extend(strings(value))
    return values


def evidence_quality_is_sufficient(evidence_item: dict) -> bool:
    values = evidence_quality_values(evidence_item)
    if not values:
        return False
    for value in values:
        tokens = set(re.split(r"[^a-z0-9]+", normalized_text(value)))
        if tokens & INSUFFICIENT_EVIDENCE_QUALITY:
            return False
    return True


def evidence_can_support_strong_claim(evidence_item: dict) -> bool:
    return (
        is_active(evidence_item)
        and is_verified(evidence_item)
        and has_evidence_provenance(evidence_item)
        and evidence_quality_is_sufficient(evidence_item)
    )


def matrix_row_active(row: dict) -> bool:
    return is_active(row) and not is_planned(row)


def active_evidence_gap_claim_ids(gaps: list[dict]) -> set[str]:
    closed_statuses = INACTIVE_STATUSES | {"closed", "filled", "resolved"}
    return {
        claim_id
        for gap in gaps
        if (claim_id := item_id(gap, "claim_id", "id"))
        and is_active(gap)
        and not is_planned(gap)
        and normalized_text(gap.get("status", "")) not in closed_statuses
    }


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


def external_reference(value) -> bool:
    if missingish(value):
        return True
    text = str(value)
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", text):
        return True
    if text.startswith("doi:") or text.startswith("arXiv:"):
        return True
    return False


def local_path_part(value: str) -> str:
    return value.split(":", 1)[0]


def looks_path_like(value) -> bool:
    if missingish(value):
        return False
    text = str(value).strip()
    if external_reference(text):
        return True
    path = local_path_part(text)
    if path.startswith(("/", "./", "../", "~")):
        return True
    if "/" in path or "\\" in path:
        return True
    return bool(Path(path).suffix)


def path_exists_or_external(value, *, path_like_only: bool = False) -> bool:
    if missingish(value):
        return True
    text = str(value)
    if external_reference(text):
        return True
    if path_like_only and not looks_path_like(text):
        return True
    return (ROOT / local_path_part(text)).exists()


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


def declared_release_surfaces() -> set[str]:
    path = ROOT / "state/ccfa.yaml"
    if not path.exists():
        return set()
    ccfa = load_doc("state/ccfa.yaml")
    return set(strings(ccfa.get("release", {}).get("surfaces", [])))


def check_declared_release_surface_status(surface_id: str, surface: dict, expected_surfaces: set[str]) -> int:
    if surface_id not in expected_surfaces:
        return 0
    status = str(surface.get("status", "")).strip().lower()
    if status in {"", "empty"} and not meaningful(surface.get("files")):
        return 0
    if status in RELEASE_SYNC_STATUSES:
        return 0
    allowed = ", ".join(sorted(RELEASE_SYNC_STATUSES))
    return error(
        f"release surface {surface_id} declared in state/ccfa.yaml must be synced; "
        f"status {status or '<missing>'} is not allowed for paper release checks; allowed: {allowed}"
    )


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


def check_source_revision_freshness(manifest: dict) -> int:
    revision = manifest.get("source_revision", {})
    if not meaningful(revision):
        return 0
    if not isinstance(revision, dict):
        return error("release manifest source_revision must be a mapping")

    code = 0
    commit = str(revision.get("commit", "")).strip().lower()
    tree = str(revision.get("tree", "")).strip().lower()
    treeish = revision.get("treeish")
    if not isinstance(treeish, str) or not treeish.strip():
        code |= error("release manifest source_revision missing treeish")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        code |= error("release manifest source_revision has invalid commit")
        return code
    if git_value("cat-file", "-t", commit) != "commit":
        code |= error(f"release manifest source_revision commit is not present: {commit}")
        return code

    expected_tree = git_value("rev-parse", "--verify", f"{commit}^{{tree}}")
    if not re.fullmatch(r"[0-9a-f]{40}", tree):
        code |= error("release manifest source_revision has invalid tree")
        return code
    if git_value("cat-file", "-t", tree) != "tree":
        code |= error(f"release manifest source_revision tree is not present: {tree}")
    elif expected_tree and tree != expected_tree:
        code |= error("release manifest source_revision tree does not match commit")
    return code


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
    expected_surfaces = declared_release_surfaces()
    if isinstance(manifest, dict):
        code |= check_source_revision_freshness(manifest)
    for surface in manifest.get("surfaces", []):
        if not isinstance(surface, dict):
            code |= error("release surface entry must be a mapping")
            continue
        surface_id = surface.get("id", "<missing>")
        code |= check_declared_release_surface_status(str(surface_id), surface, expected_surfaces)
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


def has_active_core_or_strong_claims() -> bool:
    return any(
        is_active(claim) and claim_strength(claim) in {"core", "strong"}
        for claim in doc_items("state/claim-evidence-map.yaml", "claims")
        if isinstance(claim, dict)
    )


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

    claim_by_id = {claim_id: item for item in claims if (claim_id := item_id(item, "claim_id", "id"))}
    evidence_by_id = {evidence_id: item for item in evidence if (evidence_id := item_id(item, "evidence_id", "id"))}
    claim_refs_by_id = {
        claim_id: set(strings(claim.get("evidence_ids")))
        for claim_id, claim in claim_by_id.items()
    }
    evidence_supports_by_id = {
        evidence_id: set(evidence_support_claim_ids(item))
        for evidence_id, item in evidence_by_id.items()
    }
    gap_claim_ids = active_evidence_gap_claim_ids(gaps)
    plan_claim_ids = {item_id(item, "claim_id", "id") for item in plans if item_id(item, "claim_id", "id")}

    matrix_declared_relationships: dict[tuple[str, str], set[str]] = {}
    matrix_relationships: dict[tuple[str, str], set[str]] = {}
    for row_number, row in enumerate(read_csv_rows("state/evidence-matrix.csv"), start=2):
        claim_id = str(row.get("claim_id", "")).strip()
        evidence_id = str(row.get("evidence_id", "")).strip()
        relationship = normalized_text(row.get("relationship", ""))
        if missingish(claim_id) or missingish(evidence_id):
            code |= error(f"evidence-matrix row {row_number} missing claim_id or evidence_id")
            continue
        if claim_id not in claim_ids:
            code |= error(f"evidence-matrix row {row_number} references unknown claim {claim_id}")
        if evidence_id not in evidence_ids:
            code |= error(f"evidence-matrix row {row_number} references unknown evidence {evidence_id}")
        if missingish(relationship):
            code |= error(f"evidence-matrix row {row_number} missing relationship")
            continue
        if relationship not in ALLOWED_EVIDENCE_RELATIONSHIPS:
            code |= error(f"evidence-matrix row {row_number} has invalid relationship {relationship}")
            continue
        if is_active(row):
            matrix_declared_relationships.setdefault((claim_id, evidence_id), set()).add(relationship)
        if matrix_row_active(row):
            matrix_relationships.setdefault((claim_id, evidence_id), set()).add(relationship)

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
        refs = sorted(claim_refs_by_id.get(claim_id, set()))
        for evidence_id in refs:
            if evidence_id not in evidence_ids:
                code |= error(f"claim {claim_id} references unknown evidence {evidence_id}")
                continue
            relationships = matrix_declared_relationships.get((claim_id, evidence_id), set())
            if relationships & CONTRADICT_RELATIONSHIPS:
                code |= error(
                    f"claim {claim_id} lists evidence {evidence_id} as support but evidence-matrix relationship is contradicts"
                )
            evidence_item = evidence_by_id.get(evidence_id)
            if (
                is_active(claim)
                and evidence_item
                and is_active(evidence_item)
                and claim_id not in evidence_supports_by_id.get(evidence_id, set())
                and (claim_id, evidence_id) not in matrix_relationships
            ):
                code |= error(
                    f"active claim {claim_id} references evidence {evidence_id} without reciprocal evidence support or evidence-matrix row"
                )
        strength = claim_strength(claim)
        if is_active(claim) and strength in {"core", "strong"}:
            if not has_claim_statement(claim):
                code |= error(f"{strength} claim missing statement/text/claim/summary: {claim_id}")
            if claim_id not in gap_claim_ids:
                candidate_evidence_ids = set(refs)
                candidate_evidence_ids.update(
                    evidence_id
                    for (matrix_claim_id, evidence_id), relationships in matrix_relationships.items()
                    if matrix_claim_id == claim_id and relationships & SUPPORT_RELATIONSHIPS
                )
                candidate_evidence_ids.update(
                    evidence_id
                    for evidence_id, supported_claims in evidence_supports_by_id.items()
                    if claim_id in supported_claims
                )
                verified_supports = []
                for evidence_id in candidate_evidence_ids:
                    evidence_item = evidence_by_id.get(evidence_id)
                    if not evidence_item:
                        continue
                    relationships = matrix_relationships.get((claim_id, evidence_id), set())
                    reciprocal_support = (
                        evidence_id in claim_refs_by_id.get(claim_id, set())
                        and claim_id in evidence_supports_by_id.get(evidence_id, set())
                    )
                    if relationships:
                        pair_supports_claim = bool(relationships & SUPPORT_RELATIONSHIPS) and not (
                            relationships & CONTRADICT_RELATIONSHIPS
                        )
                    else:
                        pair_supports_claim = reciprocal_support
                    if pair_supports_claim and evidence_can_support_strong_claim(evidence_item):
                        verified_supports.append(evidence_id)
                if not verified_supports:
                    code |= error(
                        f"{strength} claim lacks verified supporting evidence and no active evidence gap is registered: {claim_id}"
                    )
        if strength == "core" and claim_id not in plan_claim_ids:
            code |= error(f"core claim lacks experiment plan: {claim_id}")

    for item in evidence:
        evidence_id = item_id(item, "evidence_id", "id")
        if is_verified(item):
            if not has_evidence_provenance(item):
                code |= error(f"verified evidence lacks source/provenance/artifact/external_source: {evidence_id}")
            if not evidence_quality_is_sufficient(item):
                code |= error(f"verified evidence lacks sufficient strength/fitness/status: {evidence_id}")
        for claim_id in evidence_support_claim_ids(item):
            if claim_id not in claim_ids:
                code |= error(f"evidence {evidence_id} references unknown claim {claim_id}")
                continue
            relationships = matrix_declared_relationships.get((claim_id, evidence_id), set())
            if relationships & CONTRADICT_RELATIONSHIPS:
                code |= error(
                    f"evidence {evidence_id} claims support for {claim_id} but evidence-matrix relationship is contradicts"
                )
            claim = claim_by_id.get(claim_id)
            if (
                evidence_id
                and is_active(item)
                and claim
                and is_active(claim)
                and evidence_id not in claim_refs_by_id.get(claim_id, set())
                and (claim_id, evidence_id) not in matrix_relationships
            ):
                code |= error(
                    f"active evidence {evidence_id} supports claim {claim_id} without reciprocal claim evidence_ids or evidence-matrix row"
                )

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
    return code


def load_number_groups(registry: dict):
    numbers = []
    for group_path in strings(registry.get("groups", [])):
        if not (ROOT / group_path).exists():
            continue
        numbers.extend(doc_items(group_path, "numbers"))
    return numbers


def scalar_strings(value):
    if missingish(value):
        return []
    if isinstance(value, dict):
        return []
    if isinstance(value, (list, tuple, set)):
        values = []
        for item in value:
            values.extend(scalar_strings(item))
        return values
    return [str(value)]


def nested_field_strings(value, fields):
    values = []
    if missingish(value):
        return values
    if isinstance(value, dict):
        for field in fields:
            values.extend(nested_field_strings(value.get(field), fields))
        return values
    if isinstance(value, (list, tuple, set)):
        for item in value:
            values.extend(nested_field_strings(item, fields))
        return values
    values.append(str(value))
    return values


def load_numeric_numbers():
    registry = load_doc("state/numeric-registry.yaml") if (ROOT / "state/numeric-registry.yaml").exists() else {}
    index = load_doc("state/numbers/numeric-index.yaml") if (ROOT / "state/numbers/numeric-index.yaml").exists() else {}
    numbers = []
    numbers.extend(as_list(registry.get("numbers")))
    numbers.extend(as_list(index.get("numbers")))
    numbers.extend(load_number_groups(registry))
    return [item for item in numbers if isinstance(item, dict)]


def load_float_registry_ids():
    code = require([
        "state/claim-evidence-map.yaml",
        "state/numeric-registry.yaml",
        "state/numbers/numeric-index.yaml",
        "state/result-status.yaml",
        "lab/artifacts/result-index.yaml",
    ])
    if code:
        return code, set(), set(), set()

    claims = doc_items("state/claim-evidence-map.yaml", "claims")
    numbers = load_numeric_numbers()
    status_results = doc_items("state/result-status.yaml", "results")
    index_results = doc_items("lab/artifacts/result-index.yaml", "results")

    claim_code, claim_ids = collect_ids(claims, ["claim_id", "id"], "claims", required=False)
    number_code, numeric_ids = collect_ids(numbers, ["numeric_id", "id"], "numbers", required=False)
    status_code, status_result_ids = collect_ids(status_results, ["result_id", "id"], "state/result-status.yaml results", required=False)
    index_code, index_result_ids = collect_ids(index_results, ["result_id", "id"], "lab/artifacts/result-index.yaml results", required=False)
    result_ids = status_result_ids | index_result_ids
    return code | claim_code | number_code | status_code | index_code, claim_ids, numeric_ids, result_ids


def check_registry_references(item: dict, context: str, claim_ids: set[str], numeric_ids: set[str], result_ids: set[str]) -> int:
    code = 0
    for field in ["claim_ids", "nearby_claim_ids"]:
        for claim_id in strings(item.get(field)):
            if claim_id not in claim_ids:
                code |= error(f"{context} references unknown claim id {claim_id}")
    for numeric_id in strings(item.get("numeric_ids")):
        if numeric_id not in numeric_ids:
            code |= error(f"{context} references unknown numeric id {numeric_id}")
    for result_id in strings(item.get("result_ids")):
        if result_id not in result_ids:
            code |= error(f"{context} references unknown result id {result_id}")
    return code


def has_float_provenance(item: dict) -> bool:
    for field in PROVENANCE_FIELDS:
        if has_value(item.get(field)):
            return True
    provenance = item.get("provenance", {})
    if isinstance(provenance, dict):
        for field in PROVENANCE_FIELDS:
            if has_value(provenance.get(field)):
                return True
    return False


def check_path_field_values(item: dict, context: str, fields, *, path_like_only: bool = False) -> int:
    code = 0
    for field in fields:
        for value in leaf_values(item.get(field)):
            if not missingish(value) and not path_exists_or_external(value, path_like_only=path_like_only):
                code |= error(f"{context} has missing {field}: {value}")
    return code


def check_provenance_paths(item: dict, context: str) -> int:
    code = check_path_field_values(item, context, PROVENANCE_PATH_FIELDS, path_like_only=True)
    provenance = item.get("provenance", {})
    if isinstance(provenance, dict):
        code |= check_path_field_values(provenance, context, PROVENANCE_PATH_FIELDS, path_like_only=True)
    return code


def float_maps(floats):
    by_float_id = {}
    by_label = {}
    by_figure_id = {}
    by_table_id = {}
    for item in floats:
        if not isinstance(item, dict):
            continue
        for field, target in [
            ("float_id", by_float_id),
            ("id", by_float_id),
            ("label", by_label),
            ("figure_id", by_figure_id),
            ("table_id", by_table_id),
        ]:
            value = item.get(field)
            if not missingish(value):
                target[str(value)] = item
    return by_float_id, by_label, by_figure_id, by_table_id


def explicitly_qualitative(item: dict) -> bool:
    if item.get("qualitative") is True:
        return True
    for field in ["kind", "type", "mode", "table_type"]:
        if str(item.get(field, "")).lower() == "qualitative":
            return True
    return False


def table_requires_numeric_binding(item: dict) -> bool:
    status = str(item.get("status", "")).lower()
    return is_verified(item) or status == "final"


FIGURE_ENVIRONMENTS = {"figure", "figure*", "sidewaysfigure", "sidewaysfigure*", "wrapfigure"}
TABLE_ENVIRONMENTS = {"table", "table*", "sidewaystable", "sidewaystable*", "longtable"}


def latex_block_for_label(text: str, label: str, environments=None) -> str:
    if missingish(label):
        return ""
    environments = environments or TABLE_ENVIRONMENTS
    label_pattern = re.compile(rf"\\label\{{\s*{re.escape(str(label))}\s*\}}")
    label_match = label_pattern.search(text)
    if not label_match:
        return ""

    begin_match = None
    for match in re.finditer(r"\\begin\{([^}]+)\}", text[: label_match.start()]):
        if match.group(1) in environments:
            begin_match = match
    if begin_match is None:
        start = max(0, label_match.start() - 1000)
        end = min(len(text), label_match.end() + 1000)
        return text[start:end]

    env_name = begin_match.group(1)
    end_pattern = re.compile(rf"\\end\{{{re.escape(env_name)}\}}")
    end_match = end_pattern.search(text, label_match.end())
    if end_match is None:
        return text[begin_match.start() : min(len(text), label_match.end() + 1000)]
    return text[begin_match.start() : end_match.end()]


def includegraphics_paths(text: str) -> list[str]:
    scan_text = "\n".join(strip_tex_comment(line) for line in text.splitlines())
    pattern = re.compile(r"\\includegraphics(?:\s*\[[^\]]*\])*\s*\{([^{}]+)\}")
    return [match.group(1).strip() for match in pattern.finditer(scan_text) if match.group(1).strip()]


def asset_path_variants(value) -> set[str]:
    if missingish(value) or external_reference(value):
        return set()
    text = local_path_part(str(value)).strip().strip("{}").strip("\"'")
    if not text or "\\" in text:
        return set()
    text = re.sub(r"/+", "/", text.replace("\\", "/"))
    while text.startswith("./"):
        text = text[2:]
    variants = {text}
    if text.startswith("paper/"):
        variants.add(text[len("paper/") :])
    elif not text.startswith(("/", "../", "~")):
        variants.add(f"paper/{text}")
    for candidate in list(variants):
        suffix = Path(candidate).suffix
        if suffix:
            variants.add(candidate[: -len(suffix)])
    return {variant for variant in variants if variant}


def declared_asset_paths(*items: dict | None) -> list[tuple[str, str, set[str]]]:
    declared = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        for field in ["asset_path", "artifact_path", "path"]:
            for value in leaf_values(item.get(field)):
                variants = asset_path_variants(value)
                if not variants:
                    continue
                key = tuple(sorted(variants))
                if key in seen:
                    continue
                seen.add(key)
                declared.append((field, str(value), variants))
    return declared


def check_figure_asset_binding(item: dict, mapped_float: dict | None, label: str, ident: str, text: str) -> int:
    if missingish(label):
        return 0
    block = latex_block_for_label(text, str(label), FIGURE_ENVIRONMENTS)
    actual_paths = includegraphics_paths(block)
    if not actual_paths:
        return 0
    actual_variants = set()
    for path in actual_paths:
        actual_variants |= asset_path_variants(path)
    if not actual_variants:
        return 0

    code = 0
    for field, value, variants in declared_asset_paths(item, mapped_float):
        if not variants & actual_variants:
            sample = ", ".join(actual_paths[:5])
            code |= error(
                f"figure {ident} includegraphics asset mismatch for {field}: "
                f"expected {value}; found {sample}"
            )
    return code


def numeric_literals_in_latex(text: str) -> list[str]:
    scan_text = "\n".join(mask_latex_numeric_contexts(strip_tex_comment(line)) for line in text.splitlines())
    return [match.group(0).strip() for match in NUMERIC_LITERAL_RE.finditer(scan_text) if match.group(0).strip()]


def notation_symbol_variants(symbol: str) -> list[str]:
    raw = str(symbol).strip()
    variants = [raw]
    math_wrappers = [("$", "$"), ("\\(", "\\)"), ("\\[", "\\]")]
    for prefix, suffix in math_wrappers:
        if raw.startswith(prefix) and raw.endswith(suffix) and len(raw) > len(prefix) + len(suffix):
            core = raw[len(prefix) : -len(suffix)].strip()
            if len(core) > 1 or "\\" in core or "_" in core or "{" in core:
                variants.append(core)
    if raw.startswith("{") and raw.endswith("}") and len(raw) > 2:
        variants.append(raw[1:-1].strip())
    return [variant for variant in dict.fromkeys(variants) if variant]


def text_contains_notation_symbol(text: str, symbol: str) -> bool:
    return any(variant in text for variant in notation_symbol_variants(symbol))


def local_path_and_optional_line(value: str) -> tuple[Path, int | None]:
    text = str(value).strip()
    path_text = local_path_part(text)
    line_no = None
    suffix = text[len(path_text) :]
    if suffix.startswith(":"):
        line_text = suffix[1:]
        if line_text.isdigit():
            line_no = int(line_text)
    return ROOT / path_text, line_no


def first_defined_text(value: str) -> str | None:
    if missingish(value) or external_reference(value):
        return None
    path, line_no = local_path_and_optional_line(str(value))
    if not path.exists() or not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
    if line_no is None:
        return text
    lines = text.splitlines()
    if line_no < 1 or line_no > len(lines):
        return ""
    return lines[line_no - 1]


def normalize_macro_name(macro) -> str:
    if missingish(macro):
        return ""
    text = str(macro).strip()
    return text if text.startswith("\\") else "\\" + text


def read_balanced_braces(text: str, start: int):
    if start >= len(text) or text[start] != "{":
        return None, start
    depth = 0
    escaped = False
    chars = []
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            if depth > 0:
                chars.append(char)
            escaped = False
            continue
        if char == "\\":
            if depth > 0:
                chars.append(char)
            escaped = True
            continue
        if char == "{":
            depth += 1
            if depth > 1:
                chars.append(char)
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return "".join(chars), index + 1
            chars.append(char)
            continue
        if depth > 0:
            chars.append(char)
    return None, start


def skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def skip_optional_args(text: str, index: int) -> int:
    index = skip_ws(text, index)
    while index < len(text) and text[index] == "[":
        end = text.find("]", index + 1)
        if end == -1:
            return index
        index = skip_ws(text, end + 1)
    return index


def extract_macro_values(text: str) -> dict[str, str]:
    values = {}
    command_pattern = re.compile(r"\\(?:newcommand|renewcommand|providecommand)\*?")
    for match in command_pattern.finditer(text):
        index = skip_ws(text, match.end())
        macro = None
        if index < len(text) and text[index] == "{":
            macro, index = read_balanced_braces(text, index)
            macro = normalize_macro_name(macro)
        elif index < len(text) and text[index] == "\\":
            name_match = re.match(r"\\[A-Za-z@]+", text[index:])
            if name_match:
                macro = normalize_macro_name(name_match.group(0))
                index += len(name_match.group(0))
        if not macro:
            continue
        index = skip_optional_args(text, index)
        value, end = read_balanced_braces(text, index)
        if value is not None:
            values[macro] = value
            index = end

    def_pattern = re.compile(r"\\def\s*(\\[A-Za-z@]+)")
    for match in def_pattern.finditer(text):
        macro = normalize_macro_name(match.group(1))
        index = skip_ws(text, match.end())
        value, _ = read_balanced_braces(text, index)
        if macro and value is not None:
            values[macro] = value
    return values


def normalize_numeric_value(value) -> str:
    text = str(value).strip()
    text = re.sub(r"\\(?:text|mathrm|mathbf|mathit)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\([%&_#$])", r"\1", text)
    text = text.replace("\\,", "")
    text = text.replace("\\ ", " ")
    text = text.replace("~", " ")
    text = text.replace("{", "")
    text = text.replace("}", "")
    text = text.replace(",", "")
    text = re.sub(r"\bpercent\b", "%", text, flags=re.I)
    text = re.sub(r"\s+", "", text)
    return text.lower()


def registered_number_values(number: dict) -> list[str]:
    direct_values = []
    for field in ["value", "display_value", "reported_value", "latex_value", "macro_value"]:
        direct_values.extend(scalar_strings(number.get(field)))
    display_values = []
    display = number.get("display")
    if isinstance(display, dict):
        for field in ["value", "display_value", "reported_value", "latex_value", "macro_value", "text", "latex"]:
            display_values.extend(scalar_strings(display.get(field)))
    elif not missingish(display):
        display_values.extend(scalar_strings(display))
    return display_values or direct_values


def numeric_alias_targets(number: dict | None) -> set[str]:
    if not isinstance(number, dict):
        return set()
    targets = set()
    for field in [
        "alias_of",
        "same_as",
        "canonical_id",
        "canonical_numeric_id",
        "equivalent_numeric_id",
        "equivalent_numeric_ids",
    ]:
        targets.update(scalar_strings(number.get(field)))
    alias = number.get("alias")
    if isinstance(alias, dict):
        for field in ["of", "target", "numeric_id", "canonical_numeric_id"]:
            targets.update(scalar_strings(alias.get(field)))
    return {target for target in targets if target}


def shared_macro_is_explicit_alias(owners: set[str], number_by_id: dict[str, dict]) -> bool:
    if len(owners) < 2:
        return True
    for candidate in owners:
        if all(owner == candidate or candidate in numeric_alias_targets(number_by_id.get(owner)) for owner in owners):
            return True
    return False


def evidence_refs(item: dict) -> list[str]:
    refs = []
    for field in ["evidence_ids", "evidence_id"]:
        refs.extend(scalar_strings(item.get(field)))
    for entry in as_list(item.get("evidence")):
        if isinstance(entry, dict):
            ident = item_id(entry, "evidence_id", "id")
            if ident:
                refs.append(ident)
        elif not missingish(entry):
            refs.append(str(entry))
    return refs


def result_refs(item: dict) -> list[str]:
    refs = []
    for field in ["result_ids", "result_id"]:
        refs.extend(scalar_strings(item.get(field)))
    return refs


def path_anchor_values(item: dict) -> list[str]:
    values = []
    nested_fields = ["path", "artifact_path", "source", "uri", "url", "snapshot_path"]
    for field in ["artifact_path", "artifact_paths", "source", "sources", "snapshot_path", "snapshot_paths"]:
        values.extend(nested_field_strings(item.get(field), nested_fields))
    for field in ["artifacts", "snapshots"]:
        values.extend(nested_field_strings(item.get(field), nested_fields))
    provenance = item.get("provenance")
    if isinstance(provenance, (dict, list, tuple, set)):
        values.extend(nested_field_strings(provenance, nested_fields))
    return values


def has_scalar_anchor(item: dict) -> bool:
    for field in ["run_id", "run_ids", "snapshot", "checksum", "checksums", "sha256", "digest"]:
        if scalar_strings(item.get(field)):
            return True
    provenance = item.get("provenance")
    if isinstance(provenance, dict):
        for field in ["run_id", "run_ids", "snapshot", "checksum", "checksums", "sha256", "digest"]:
            if scalar_strings(provenance.get(field)):
                return True
    return False


def result_numeric_refs(result: dict):
    refs = []
    missing_entry_id = False
    field_present = any(field in result for field in ["numeric_id", "numeric_ids", "numbers"])
    refs.extend(scalar_strings(result.get("numeric_id")))
    refs.extend(scalar_strings(result.get("numeric_ids")))
    if "numbers" in result:
        numbers = result.get("numbers")
        if isinstance(numbers, dict):
            for key, value in numbers.items():
                if isinstance(value, dict):
                    refs.append(item_id(value, "numeric_id", "id") or str(key))
                else:
                    refs.append(str(key))
        else:
            for entry in as_list(numbers):
                if isinstance(entry, dict):
                    ident = item_id(entry, "numeric_id", "id")
                    if ident:
                        refs.append(ident)
                    else:
                        missing_entry_id = True
                elif not missingish(entry):
                    refs.append(str(entry))
    return refs, field_present, missing_entry_id


VALID_EXCEPTION_MATCH_SCOPES = {"literal", "context", "literal_or_context"}


def normalize_exception_match_scope(scope) -> str:
    return str(scope or "literal").strip().lower().replace("-", "_")


def exception_matches(exception: dict, path: Path, literal: str, context: str) -> bool:
    path_pattern = exception.get("path_pattern")
    if path_pattern is not None and not path_pattern.search(rel(path)):
        return False
    pattern = exception["pattern"]
    scope = exception["match_scope"]
    literal_match = bool(pattern.fullmatch(literal))
    if scope == "literal":
        return literal_match
    context_match = bool(pattern.search(context))
    if scope == "context":
        return context_match
    return literal_match or context_match


def strip_tex_comment(line: str) -> str:
    for index, char in enumerate(line):
        if char != "%":
            continue
        slash_count = 0
        cursor = index - 1
        while cursor >= 0 and line[cursor] == "\\":
            slash_count += 1
            cursor -= 1
        if slash_count % 2 == 0:
            return line[:index]
    return line


def mask_latex_numeric_contexts(text: str) -> str:
    command_names = "|".join(re.escape(name) for name in MASKED_NUMERIC_CONTEXT_COMMANDS)
    pattern = re.compile(rf"\\(?:{command_names})(?:\s*\[[^\]]*\])*(?:\s*\{{[^{{}}]*\}})+")
    return pattern.sub(" ", text)


def iter_paper_numeric_literals():
    for path in paper_content_tex_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            scan_line = mask_latex_numeric_contexts(strip_tex_comment(line))
            for match in NUMERIC_LITERAL_RE.finditer(scan_line):
                literal = match.group(0).strip()
                if literal:
                    yield path, line_no, literal, line.strip()


def check_unregistered_numeric_literals(verified_values: set[str]) -> int:
    if not paper_looks_populated():
        return 0
    code = 0
    exceptions = doc_items("state/numbers/exceptions.yaml", "exceptions")
    valid_exceptions = []
    for index, item in enumerate(exceptions, start=1):
        if not isinstance(item, dict):
            code |= error(f"state/numbers/exceptions.yaml exceptions[{index}] must be a mapping")
            continue
        pattern = item.get("pattern")
        reason = item.get("reason")
        if missingish(pattern) or missingish(reason):
            code |= error(f"state/numbers/exceptions.yaml exceptions[{index}] missing pattern/reason")
            continue
        try:
            compiled_pattern = re.compile(str(pattern))
        except re.error as exc:
            code |= error(f"state/numbers/exceptions.yaml exceptions[{index}] invalid regex: {exc}")
            continue
        match_scope = normalize_exception_match_scope(item.get("match_scope"))
        if match_scope not in VALID_EXCEPTION_MATCH_SCOPES:
            code |= error(
                "state/numbers/exceptions.yaml "
                f"exceptions[{index}] invalid match_scope {item.get('match_scope')}; "
                "expected literal, context, or literal_or_context"
            )
            continue
        path_pattern = item.get("path_pattern")
        compiled_path_pattern = None
        if not missingish(path_pattern):
            try:
                compiled_path_pattern = re.compile(str(path_pattern))
            except re.error as exc:
                code |= error(f"state/numbers/exceptions.yaml exceptions[{index}] invalid path_pattern regex: {exc}")
                continue
        valid_exceptions.append(
            {
                "pattern": compiled_pattern,
                "reason": str(reason),
                "match_scope": match_scope,
                "path_pattern": compiled_path_pattern,
            }
        )

    for path, line_no, literal, context in iter_paper_numeric_literals():
        normalized = normalize_numeric_value(literal)
        if normalized in verified_values:
            continue
        if any(exception_matches(exception, path, literal, context) for exception in valid_exceptions):
            continue
        code |= error(
            "unregistered numeric literal in populated paper content: "
            f"{literal} at {rel(path)}:{line_no}"
        )
    return code


def check_result_status():
    code = require(["state/result-status.yaml", "lab/artifacts/result-index.yaml", "state/claim-evidence-map.yaml"])
    if code:
        return code
    status_results = doc_items("state/result-status.yaml", "results")
    index_results = doc_items("lab/artifacts/result-index.yaml", "results")
    claims = doc_items("state/claim-evidence-map.yaml", "claims")
    numbers = load_numeric_numbers()

    code |= collect_ids(status_results, ["result_id", "id"], "state/result-status.yaml results", required=False)[0]
    index_code, index_ids = collect_ids(index_results, ["result_id", "id"], "lab/artifacts/result-index.yaml results", required=False)
    code |= index_code
    claim_ids = collect_ids(claims, ["claim_id", "id"], "claims", required=False)[1]
    number_ids = collect_ids(numbers, ["numeric_id", "id"], "numbers", required=False)[1]
    verified_result_ids = {
        result_id
        for result in status_results + index_results
        if is_verified(result) and (result_id := item_id(result, "result_id", "id"))
    }

    for result in status_results:
        result_id = item_id(result, "result_id", "id")
        if is_verified(result) and result_id not in index_ids:
            code |= error(f"verified result missing from result-index: {result_id}")
    for result in index_results:
        result_id = item_id(result, "result_id", "id")
        verified = is_verified(result) or result_id in verified_result_ids
        if verified:
            source_artifact_values = path_anchor_values(result)
            if not (source_artifact_values or evidence_refs(result)):
                code |= error(f"verified result lacks source/artifacts/evidence: {result_id}")
            for value in source_artifact_values:
                if not path_exists_or_external(value):
                    code |= error(f"verified result has missing artifact/source: {result_id} {value}")
        for claim_id in strings(result.get("claims_supported")):
            if claim_ids and claim_id not in claim_ids:
                code |= error(f"result {result_id} supports unknown claim {claim_id}")
        refs, field_present, missing_entry_id = result_numeric_refs(result)
        if field_present and missing_entry_id:
            code |= error(f"result {result_id} numbers entries must include numeric_id/id")
        for numeric_id in refs:
            if numeric_id not in number_ids:
                code |= error(f"result {result_id} references unknown numeric id {numeric_id}")
    return code


def check_numeric_consistency():
    code = require([
        "state/numeric-registry.yaml",
        "state/numbers/numeric-index.yaml",
        "state/numbers/macros.yaml",
        "state/numbers/exceptions.yaml",
        "state/result-status.yaml",
        "paper/generated/results-macros.tex",
        "lab/artifacts/result-index.yaml",
        "lab/research/evidence.yaml",
    ])
    if code:
        return code

    macro_doc = load_doc("state/numbers/macros.yaml")
    content_text = read_paper_content_tex()
    evidence_ids = collect_ids(doc_items("lab/research/evidence.yaml", "evidence"), ["evidence_id", "id"], "evidence", required=False)[1]
    claims = doc_items("state/claim-evidence-map.yaml", "claims")
    numbers = load_numeric_numbers()
    index_results = doc_items("lab/artifacts/result-index.yaml", "results")
    result_map = {item_id(result, "result_id", "id"): result for result in index_results if item_id(result, "result_id", "id")}
    result_ids = set(result_map)

    number_code, number_ids = collect_ids(numbers, ["numeric_id", "id"], "numbers", required=False)
    code |= number_code
    number_by_id = {item_id(number, "numeric_id", "id"): number for number in numbers if item_id(number, "numeric_id", "id")}

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
    generated_macro_values = extract_macro_values(macro_text)
    macro_owners: dict[str, set[str]] = {}

    for numeric_id, macro in macro_map.items():
        if number_ids and numeric_id not in number_ids:
            code |= error(f"macro map references unknown numeric id {numeric_id}")
        normalized = normalize_macro_name(macro)
        if normalized and numeric_id:
            macro_owners.setdefault(normalized, set()).add(str(numeric_id))
        if normalized not in generated_macros:
            code |= error(f"macro map for {numeric_id} missing generated macro {normalized}")

    verified_literal_values = set()
    for number in numbers:
        numeric_id = item_id(number, "numeric_id", "id")
        if is_verified(number):
            verified_literal_values.update(normalize_numeric_value(value) for value in registered_number_values(number))
        for evidence_id in evidence_refs(number):
            if evidence_id not in evidence_ids:
                code |= error(f"number {numeric_id} references unknown evidence {evidence_id}")
        display = number.get("display", {}) if isinstance(number.get("display"), dict) else {}
        macro = number.get("latex_macro") or display.get("latex_macro") or macro_map.get(numeric_id)
        if not missingish(macro):
            normalized = normalize_macro_name(macro)
            if normalized and numeric_id:
                macro_owners.setdefault(normalized, set()).add(str(numeric_id))
            if normalized not in generated_macros:
                code |= error(f"number {numeric_id} expects missing generated macro {normalized}")
            if is_verified(number) and normalized not in content_text:
                code |= error(f"verified number macro is not used in paper content: {numeric_id} {normalized}")
            if normalized in generated_macro_values:
                expected_values = {normalize_numeric_value(value) for value in registered_number_values(number)}
                generated_value = normalize_numeric_value(generated_macro_values[normalized])
                if expected_values and generated_value not in expected_values:
                    code |= error(f"generated macro value drifts from registered value: {numeric_id} {normalized}")
                if is_verified(number):
                    verified_literal_values.add(generated_value)
                    verified_literal_values.update(expected_values)
        if is_verified(number):
            number_evidence = evidence_refs(number)
            if not number_evidence:
                code |= error(f"verified number lacks evidence: {numeric_id}")
            valid_path_anchors = []
            for value in path_anchor_values(number):
                if path_exists_or_external(value):
                    valid_path_anchors.append(value)
                else:
                    code |= error(f"verified number has missing artifact/source: {numeric_id} {value}")
            resolved_results = []
            for result_id in result_refs(number):
                if result_id in result_ids:
                    resolved_results.append(result_id)
                    result = result_map[result_id]
                    refs, field_present, _missing_entry_id = result_numeric_refs(result)
                    if field_present and numeric_id not in refs:
                        code |= error(f"result-index entry {result_id} does not link back to numeric id {numeric_id}")
                else:
                    code |= error(f"number {numeric_id} references missing result-index result_id {result_id}")
            if not (valid_path_anchors or has_scalar_anchor(number) or resolved_results):
                code |= error(f"verified number lacks reproducibility anchor: {numeric_id}")
        derived = number.get("derived", {}) if isinstance(number.get("derived"), dict) else {}
        for dep_id in strings(derived.get("depends_on")):
            if number_ids and dep_id not in number_ids:
                code |= error(f"derived number {numeric_id} depends on unknown number {dep_id}")

    for macro, owners in sorted(macro_owners.items()):
        if len(owners) > 1 and not shared_macro_is_explicit_alias(owners, number_by_id):
            code |= error(f"generated macro has multiple numeric owners without explicit alias: {macro} {sorted(owners)}")

    code |= check_unregistered_numeric_literals(verified_literal_values)
    code |= check_result_status()
    return code


def check_reference_existence():
    code = require(["paper/refs.bib", "lab/research/reference-ledger.yaml", "lab/research/citation-ledger.yaml"])
    if code:
        return code
    bib_text = (ROOT / "paper/refs.bib").read_text(encoding="utf-8")
    bib_keys = extract_bibkeys(bib_text)
    references = doc_items("lab/research/reference-ledger.yaml", "references")
    citation_ledger = load_doc("lab/research/citation-ledger.yaml")
    citations = citation_ledger.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    code |= collect_ids(references, ["reference_id", "id", "bibkey"], "references", required=False)[0]
    code |= collect_ids(citations, ["citation_id", "id", "bibkey"], "citations", required=False)[0]

    reference_keys = set()
    for ref in references:
        for key in reference_bibkeys(ref):
            reference_keys.add(key)
            if bib_keys and key not in bib_keys:
                code |= error(f"reference ledger bibkey missing from refs.bib: {key}")
    for citation in citations:
        citation_id = item_id(citation, "citation_id", "id", "bibkey")
        for key in citation_bibkeys(citation):
            if key not in bib_keys and key not in reference_keys:
                code |= error(f"citation {citation_id} references unknown bibkey {key}")

    paper_keys = extract_cite_keys(read_paper_tex())
    citation_keys = set()
    for citation in citations:
        citation_keys.update(citation_bibkeys(citation))
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
    code = require([
        "paper/refs.bib",
        "lab/research/reference-ledger.yaml",
        "lab/research/citation-ledger.yaml",
        "lab/research/related-work-map.yaml",
    ])
    if code:
        return code
    bib_keys = extract_bibkeys((ROOT / "paper/refs.bib").read_text(encoding="utf-8"))
    references = doc_items("lab/research/reference-ledger.yaml", "references")
    citation_ledger = load_doc("lab/research/citation-ledger.yaml")
    citations = citation_ledger.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    areas = doc_items("lab/research/related-work-map.yaml", "areas")
    paper_keys = extract_cite_keys(read_paper_content_tex())
    reference_keys = set()
    for ref in references:
        reference_keys.update(reference_bibkeys(ref))
    citation_keys = set()
    for citation in citations:
        citation_keys.update(citation_bibkeys(citation))

    if paper_keys and not citation_keys:
        code |= error("paper has citations but citation-ledger is empty")
    for key in paper_keys:
        if key not in bib_keys:
            code |= error(f"paper cites missing BibTeX key: {key}")
        if key not in reference_keys:
            code |= error(f"paper cites key not registered in reference-ledger: {key}")
        if key not in citation_keys:
            code |= error(f"paper cites key not registered in citation-ledger: {key}")

    for citation in citations:
        citation_id = item_id(citation, "citation_id", "id", "bibkey")
        keys = citation_bibkeys(citation)
        fitness_status = str(citation.get("fitness_status", "")).strip().lower()
        if active_now(citation):
            if not keys:
                code |= error(f"active citation {citation_id} missing bibkey")
            if not has_any_field(citation, ["purpose", "intent"]):
                code |= error(f"citation {citation_id} missing purpose/intent")
            if not has_any_field(citation, CITATION_CONTEXT_FIELDS):
                code |= error(f"citation {citation_id} missing context/locator")
            if missingish(citation.get("fitness_status")):
                code |= error(f"citation {citation_id} missing fitness_status")
            elif fitness_status not in CITATION_FITNESS_STATUSES:
                allowed = ", ".join(sorted(CITATION_FITNESS_STATUSES))
                code |= error(f"citation {citation_id} has invalid fitness_status {citation.get('fitness_status')}; allowed: {allowed}")
            for key in keys:
                if key not in paper_keys:
                    code |= error(f"active citation {citation_id} key not cited in paper content: {key}")
        if fitness_status in WEAK_CITATION_FITNESS_STATUSES and not has_any_field(citation, ["notes", "replacement_candidates"]):
            code |= error(f"citation {citation_id} has {fitness_status} fitness without notes or replacement_candidates")

    code |= check_citation_bulk_import_state(citation_ledger, citations)

    for area in areas:
        area_id = item_id(area, "area_id", "id")
        cited_keys = key_strings(area.get("cited_keys") or area.get("bibkeys"))
        for key in cited_keys:
            if key not in reference_keys and key not in bib_keys:
                code |= error(f"related-work area {area_id} cites unknown bibkey {key}")
            else:
                if key not in reference_keys:
                    code |= error(f"related-work area {area_id} cites key not registered in reference-ledger: {key}")
                if key not in bib_keys:
                    code |= error(f"related-work area {area_id} cites key missing from refs.bib: {key}")
        if area.get("required_citation_types") and not cited_keys:
            missing_candidates = area.get("missing_candidates")
            if not meaningful(missing_candidates):
                code |= error(f"related-work area {area_id} has requirements but no cited keys or missing candidates")
            elif not missing_candidate_notes(area):
                code |= error(f"related-work area {area_id} lists missing candidates without notes")
    return code


def check_float_placement():
    code = require(["state/float-placement-map.yaml", "lab/artifacts/figure-index.yaml", "lab/artifacts/table-index.yaml"])
    if code:
        return code
    floats = doc_items("state/float-placement-map.yaml", "floats")
    figures = doc_items("lab/artifacts/figure-index.yaml", "figures")
    tables = doc_items("lab/artifacts/table-index.yaml", "tables")
    code |= collect_ids(floats, ["float_id", "id", "label"], "floats", required=False)[0]
    figure_ids = collect_ids(figures, ["figure_id", "id"], "figures", required=False)[1]
    table_ids = collect_ids(tables, ["table_id", "id"], "tables", required=False)[1]
    registry_code, claim_ids, numeric_ids, result_ids = load_float_registry_ids()
    code |= registry_code
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
        if is_active(item):
            figure_id = item.get("figure_id")
            table_id = item.get("table_id")
            if not missingish(figure_id) and str(figure_id) not in figure_ids:
                code |= error(f"active float {float_id} references unknown figure_id {figure_id}")
            if not missingish(table_id) and str(table_id) not in table_ids:
                code |= error(f"active float {float_id} references unknown table_id {table_id}")
            if not is_planned(item):
                if missingish(label):
                    code |= error(f"active float missing label: {float_id}")
                elif str(label) not in labels:
                    code |= error(f"float map references label absent from paper tex: {label}")
                code |= check_path_field_values(item, f"float {float_id}", ["asset_path", "tex_source", "caption_source"])
        code |= check_registry_references(item, f"float {float_id}", claim_ids, numeric_ids, result_ids)
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
    floats = doc_items("state/float-placement-map.yaml", "floats")
    code |= collect_ids(figures, ["figure_id", "id"], "figures", required=False)[0]
    code |= collect_ids(tables, ["table_id", "id"], "tables", required=False)[0]
    registry_code, claim_ids, numeric_ids, result_ids = load_float_registry_ids()
    code |= registry_code
    text = read_paper_tex()
    labels = extract_labels(text)
    by_float_id, by_label, _, _ = float_maps(floats)

    for kind, items in [("figure", figures), ("table", tables)]:
        for item in items:
            ident = item_id(item, f"{kind}_id", "id") or "<missing>"
            context = f"{kind} {ident}"
            label = item.get("label")
            float_id = item.get("float_id")
            mapped_float = None
            if not missingish(float_id):
                mapped_float = by_float_id.get(str(float_id))
            if mapped_float is None and not missingish(label):
                mapped_float = by_label.get(str(label))

            code |= check_path_field_values(item, context, ["path", "asset_path"])
            code |= check_provenance_paths(item, context)
            code |= check_registry_references(item, context, claim_ids, numeric_ids, result_ids)

            if is_active(item):
                if missingish(label) and missingish(float_id):
                    code |= error(f"active {kind} {ident} missing label or float_id")
                elif mapped_float is None:
                    code |= error(f"{kind} {ident} is not represented in state/float-placement-map.yaml")

                mapped_label = label
                if missingish(mapped_label) and isinstance(mapped_float, dict):
                    mapped_label = mapped_float.get("label")
                if not missingish(mapped_label) and str(mapped_label) not in labels:
                    code |= error(f"{kind} {ident} label absent from paper tex: {mapped_label}")

                if not is_planned(item) and not has_float_provenance(item):
                    code |= error(f"{kind} {ident} missing provenance")

                if kind == "figure" and not missingish(mapped_label):
                    code |= check_figure_asset_binding(item, mapped_float, str(mapped_label), ident, text)

            if kind == "table" and table_requires_numeric_binding(item):
                has_numeric_binding = strings(item.get("numeric_ids")) or strings(item.get("result_ids"))
                if not has_numeric_binding and explicitly_qualitative(item):
                    table_label = mapped_label if not missingish(mapped_label) else label
                    numeric_literals = numeric_literals_in_latex(latex_block_for_label(text, str(table_label)))
                    if numeric_literals:
                        sample = ", ".join(numeric_literals[:5])
                        code |= error(
                            f"table {ident} marked qualitative but contains numeric literals without "
                            f"numeric_ids or result_ids: {sample}"
                        )
                elif not has_numeric_binding:
                    code |= error(f"table {ident} verified/final without numeric_ids or result_ids")
    code |= check_float_placement()
    return code


def check_notation():
    code = require(["state/notation.yaml", "state/terminology.yaml"])
    if code:
        return code
    symbols = doc_items("state/notation.yaml", "symbols")
    terms = doc_items("state/terminology.yaml", "terms")
    seen_symbols = {}
    paper_content = read_paper_content_tex()
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
        if active_now(item):
            if not text_contains_notation_symbol(paper_content, symbol):
                code |= error(f"active notation symbol not used in paper content: {symbol}")
            if missingish(first_defined):
                code |= error(f"active notation symbol missing first_defined: {symbol}")
        if not missingish(first_defined):
            if not path_exists_or_external(first_defined):
                code |= error(f"notation symbol {symbol} has missing first_defined path: {first_defined}")
            target_text = first_defined_text(str(first_defined))
            if target_text is not None and not text_contains_notation_symbol(target_text, symbol):
                code |= error(f"notation symbol {symbol} not found at first_defined: {first_defined}")

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
    elif has_active_core_or_strong_claims():
        code |= check_claim_evidence()
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
