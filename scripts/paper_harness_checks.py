#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import csv
import fnmatch
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
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
STRONG_CITATION_FITNESS_STATUSES = {"strong", "adequate"}
CITATION_CONTEXT_FIELDS = ("context", "locator", "section", "quote")
CITATION_BULK_CONTEXT_THRESHOLD = 3
CITATION_BULK_IMPORT_REQUIRED_FIELDS = ("bulk_import_status", "migration_source", "fitness_review_status")
CITATION_AUDIT_REPORT_SAMPLE_LIMIT = 5
CITATION_WORKSHEET_SCHEMA_VERSION = "citation-sentence-review-worksheet-v1"
CITATION_WORKSHEET_SOURCE_REVIEW_STATUSES = {"not-started", "in-review", "reviewed", "blocked"}
CITATION_REVIEWED_DECISIONS = {"strong", "adequate", "weak", "missing-better-source"}
GENERIC_UNAUDITED_CITATION_RE = re.compile(
    r"(?:"
    r"unaudited"
    r"|not[-\s]+(?:sentence[-\s]+)?audited"
    r"|sentence[-\s]+level citation fitness not audited"
    r"|migrated source context"
    r"|citation present in migrated"
    r"|manual citation fitness review remains pending"
    r")",
    re.I,
)
CITE_COMMANDS = (
    "autocite",
    "cite",
    "citealp",
    "citealt",
    "citeauthor",
    "citefullauthor",
    "citep",
    "citet",
    "citeyear",
    "citeyearpar",
    "footcite",
    "parencite",
    "supercite",
    "textcite",
)
FIGURE_LABEL_PREFIXES = ("fig:", "figure:")
TABLE_LABEL_PREFIXES = ("tab:", "table:")
FLOAT_LABEL_PREFIXES = FIGURE_LABEL_PREFIXES + TABLE_LABEL_PREFIXES
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
    *CITE_COMMANDS,
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
    "paper/sections/00_title.tex",
    "paper/sections/01_abstract.tex",
    "paper/sections/02_intro.tex",
    "paper/sections/03_related.tex",
    "paper/sections/04_method.tex",
    "paper/sections/05_exp.tex",
    "paper/sections/06_conclusion.tex",
    "paper/sections/07_limitations.tex",
    "paper/sections/08_acknowledgement.tex",
    "paper/sections/10_appendix.tex",
]
# NN_name convention: first digit 0=body/1=appendix, second digit=order within
# that group. See paper/ANATOMY.md and .agent/anatomy-policy.md.
NN_NAME_RE = re.compile(r"^[01]\d_[a-z][a-z0-9_]*$")
SECTION_INPUT_FILES = [
    "00_title",
    "01_abstract",
    "02_intro",
    "03_related",
    "04_method",
    "05_exp",
    "06_conclusion",
    "07_limitations",
    "10_appendix",
]
FIGURE_ASSET_EXTENSIONS = (".pdf", ".png", ".jpg", ".jpeg")
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
VENUE_EXPORT_PAPER_ITEMS = ["sections", "figures", "tables", "generated", "refs.bib", "macros.tex"]
RELEASE_ROOT_FILES = {"README.md"}
RELEASE_SYNC_STATUSES = {"synced", "fresh", "exported"}
RELEASE_MANIFEST_VERSION = "release-manifest-v1"
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
RELEASE_FLATTEN_SOURCE_SURFACE = "arxiv"
RELEASE_FLATTEN_ID = "arxiv-flat"
RELEASE_FLATTEN_PATH = f"release/{RELEASE_FLATTEN_ID}"
RELEASE_FLATTEN_STYLE_PATTERNS = ("*.cls", "*.sty", "*.bst")
RELEASE_FLATTEN_ASSET_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".eps", ".ps", ".tif", ".tiff", ".svg",
    ".pdf_tex", ".pdf_t", ".pstex_t",
}
RELEASE_FLATTEN_ASSET_DIRS = ("figures", "tables", "generated")
RELEASE_FLATTEN_STATUSES = {"flattened", "skipped-no-latexpand", "skipped-no-main", "error"}
RELEASE_FLATTEN_SRCS_RE = re.compile(r"(?:figures|tables)/srcs/")
# Style files (*.cls/*.sty/*.bst) are copied to the flat bundle root, so any
# `{style/NAME}` reference in the flattened main.tex (e.g. \usepackage,
# \documentclass, \bibliographystyle) must drop the `style/` prefix to resolve.
RELEASE_FLATTEN_STYLE_RE = re.compile(r"\{style/")


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


def generic_unaudited_citation_signature(signature: tuple[str, ...]) -> bool:
    return any(GENERIC_UNAUDITED_CITATION_RE.search(value) for value in signature if value)


def check_citation_bulk_import_state(citation_ledger: dict, citations: list[dict]) -> int:
    code = 0
    repeated_contexts: dict[tuple[str, ...], list[tuple[str, str]]] = {}
    for citation in citations:
        if not isinstance(citation, dict) or not active_now(citation):
            continue
        fitness_status = str(citation.get("fitness_status", "")).strip().lower()
        signature = citation_context_signature(citation)
        if not any(signature):
            continue
        citation_id = item_id(citation, "citation_id", "id", "bibkey")
        repeated_contexts.setdefault(signature, []).append((citation_id, fitness_status))

    missing_fields = [field for field in CITATION_BULK_IMPORT_REQUIRED_FIELDS if not meaningful(citation_ledger.get(field))]
    for signature, entries in repeated_contexts.items():
        if len(entries) < CITATION_BULK_CONTEXT_THRESHOLD:
            continue
        sample = ", ".join(citation_id for citation_id, _status in entries[:3])
        statuses = {status for _citation_id, status in entries if status}
        weak_only = bool(statuses) and statuses <= WEAK_CITATION_FITNESS_STATUSES
        if missing_fields:
            missing = ", ".join(missing_fields)
            required = ", ".join(CITATION_BULK_IMPORT_REQUIRED_FIELDS)
            label = "repeated weak citation contexts" if weak_only else "repeated citation contexts"
            code |= error(
                f"citation-ledger has {label} "
                f"({sample}); add top-level bulk migration state fields: {missing} "
                f"(required: {required})"
            )
        if statuses & STRONG_CITATION_FITNESS_STATUSES and generic_unaudited_citation_signature(signature):
            code |= error(
                "citation-ledger has repeated strong/adequate citation contexts marked as unaudited: "
                f"{sample}"
            )
    return code


DEFINITIONAL_NOTATION_CONTEXT_RE = re.compile(
    r"\b(?:denote|denotes|denoted|define|defines|defined|let|represent|represents|represented)\b"
    r"|\bstands?\s+for\b"
    r"|\bwe\s+use\b"
    r"|\bas\s+(?:a|an|the)\b",
    re.I,
)
NOTATION_COMMAND_RE = re.compile(
    r"\\(?:"
    r"alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|lambda|mu|nu|xi|"
    r"pi|rho|sigma|tau|upsilon|phi|varphi|chi|psi|omega|"
    r"Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega|"
    r"mathcal|mathbf|mathbb|mathrm|operatorname"
    r")\b"
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


def evidence_can_support_verified_result(evidence_item: dict) -> bool:
    return (
        is_active(evidence_item)
        and not is_planned(evidence_item)
        and is_verified(evidence_item)
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


def tex_without_comments(text: str) -> str:
    return "\n".join(strip_tex_comment(line) for line in text.splitlines())


def resolve_tex_input(current: Path, value: str) -> Path | None:
    target = value.strip().strip("{}").strip()
    if not target or "\\" in target:
        return None
    path = Path(target)
    if path.suffix == "":
        path = path.with_suffix(".tex")
    candidates = []
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.append(current.parent / path)
        candidates.append(ROOT / "paper" / path)
    paper_root = (ROOT / "paper").resolve()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.exists() and resolved.suffix == ".tex":
            try:
                resolved.relative_to(paper_root)
            except ValueError:
                continue
            return resolved
    return None


def tex_input_paths(path: Path) -> list[Path]:
    try:
        text = tex_without_comments(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return []
    paths = []
    patterns = [
        re.compile(r"\\(?:input|include)\s*\{([^{}]+)\}"),
        re.compile(r"\\(?:input|include)\s+(?!\{)([A-Za-z0-9_./:+-]+)"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            target = resolve_tex_input(path, match.group(1))
            if target is not None:
                paths.append(target)
    for match in re.finditer(r"\\InputIfFileExists\s*\{([^{}]+)\}", text):
        target = resolve_tex_input(path, match.group(1))
        if target is not None:
            paths.append(target)
    return paths


def active_paper_tex_files() -> list[Path]:
    paper = ROOT / "paper"
    if not paper.exists():
        return []
    main = paper / "main.tex"
    if not main.exists():
        return sorted(paper.rglob("*.tex"))
    seen: set[Path] = set()
    ordered: list[Path] = []

    def visit(path: Path):
        resolved = path.resolve()
        if resolved in seen:
            return
        seen.add(resolved)
        ordered.append(resolved)
        for child in tex_input_paths(resolved):
            visit(child)

    visit(main)
    return ordered


def paper_tex_files():
    return active_paper_tex_files()


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
    text = tex_without_comments(text)
    command_names = "|".join(re.escape(name) for name in sorted(CITE_COMMANDS, key=len, reverse=True))
    pattern = re.compile(rf"\\(?:{command_names})\*?(?:\[[^\]]*\])*\{{([^}}]*)\}}", flags=re.I)
    for match in pattern.finditer(text):
        for key in match.group(1).split(","):
            key = key.strip()
            if key:
                keys.add(key)
    return keys


def iter_paper_citation_occurrences():
    command_names = "|".join(re.escape(name) for name in sorted(CITE_COMMANDS, key=len, reverse=True))
    pattern = re.compile(rf"\\({command_names})\*?(?:\s*\[[^\]]*\])*\s*\{{([^}}]*)\}}", flags=re.I)
    for path in paper_content_tex_files():
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            scan_line = strip_tex_comment(line)
            for match in pattern.finditer(scan_line):
                keys = [key.strip() for key in match.group(2).split(",") if key.strip()]
                if not keys:
                    continue
                yield {
                    "path": path,
                    "line": line_no,
                    "path_line": f"{rel_posix(path)}:{line_no}",
                    "command": "\\" + match.group(1),
                    "keys": keys,
                    "context": line.strip(),
                }


def citation_occurrences_by_key() -> dict[str, list[dict]]:
    by_key: dict[str, list[dict]] = {}
    for occurrence in iter_paper_citation_occurrences():
        for key in occurrence["keys"]:
            by_key.setdefault(key, []).append(occurrence)
    return by_key


def citation_locator_values(citation: dict) -> list[str]:
    locators = []
    for field in ("locator", "locators"):
        locators.extend(strings(citation.get(field)))
    return list(dict.fromkeys(locators))


def citation_audit_entry(citation: dict, occurrences_by_key: dict[str, list[dict]], paper_keys: set[str]) -> dict:
    citation_id = item_id(citation, "citation_id", "id", "bibkey")
    keys = citation_bibkeys(citation)
    fitness_status = str(citation.get("fitness_status", "")).strip().lower() or None
    active = active_now(citation)
    signature = citation_context_signature(citation)
    ledger_locators = citation_locator_values(citation)
    paper_locations = []
    sample_occurrences = []
    for occurrence in (occurrence for key in keys for occurrence in occurrences_by_key.get(key, [])):
        if occurrence["path_line"] not in paper_locations:
            paper_locations.append(occurrence["path_line"])
        if len(sample_occurrences) < CITATION_AUDIT_REPORT_SAMPLE_LIMIT:
            sample_occurrences.append(
                {
                    "path": rel_posix(occurrence["path"]),
                    "line": occurrence["line"],
                    "path_line": occurrence["path_line"],
                    "command": occurrence["command"],
                    "keys": occurrence["keys"],
                    "context": occurrence["context"],
                }
            )
    unmatched_locators = [locator for locator in ledger_locators if locator not in set(paper_locations)]
    warnings = []
    if active:
        if not keys:
            warnings.append("missing bibkey")
        if not has_any_field(citation, ["purpose", "intent"]):
            warnings.append("missing purpose/intent")
        if not has_any_field(citation, CITATION_CONTEXT_FIELDS):
            warnings.append("missing context/locator")
        if not fitness_status:
            warnings.append("missing fitness_status")
        elif fitness_status not in CITATION_FITNESS_STATUSES:
            warnings.append(f"invalid fitness_status {citation.get('fitness_status')}")
        for key in keys:
            if key not in paper_keys:
                warnings.append(f"key not cited in paper content: {key}")
    if unmatched_locators:
        warnings.append("ledger locator not found in active paper content")
    return {
        "citation_id": citation_id,
        "active": active,
        "bibkeys": keys,
        "fitness_status": fitness_status,
        "purpose": citation.get("purpose") or citation.get("intent"),
        "has_context_or_locator": has_any_field(citation, CITATION_CONTEXT_FIELDS),
        "has_locator": bool(ledger_locators),
        "generic_unaudited_context": generic_unaudited_citation_signature(signature),
        "ledger_locators": ledger_locators,
        "unmatched_ledger_locators": unmatched_locators,
        "paper_occurrence_count": len(paper_locations),
        "sample_paper_occurrences": sample_occurrences,
        "warnings": warnings,
    }


def build_citation_audit_report() -> dict:
    citation_ledger = load_doc("lab/research/citation-ledger.yaml")
    citations = citation_ledger.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    occurrences_by_key = citation_occurrences_by_key()
    paper_keys = set(occurrences_by_key)
    active_citations = [citation for citation in citations if isinstance(citation, dict) and active_now(citation)]
    active_ledger_keys = {
        key
        for citation in active_citations
        for key in citation_bibkeys(citation)
    }
    entries = [
        citation_audit_entry(citation, occurrences_by_key, paper_keys)
        for citation in citations
        if isinstance(citation, dict)
    ]
    status_counts: dict[str, int] = {}
    for citation in active_citations:
        status = str(citation.get("fitness_status", "")).strip().lower() or "missing"
        status_counts[status] = status_counts.get(status, 0) + 1
    entries_with_locator = [entry for entry in entries if entry["active"] and entry["has_locator"]]
    generic_entries = [entry for entry in entries if entry["active"] and entry["generic_unaudited_context"]]
    warning_entries = [entry for entry in entries if entry["warnings"]]
    return {
        "report_version": "citation-audit-report-v1",
        "citation_file": "lab/research/citation-ledger.yaml",
        "sample_limit": CITATION_AUDIT_REPORT_SAMPLE_LIMIT,
        "bulk_import_status": citation_ledger.get("bulk_import_status"),
        "fitness_review_status": citation_ledger.get("fitness_review_status"),
        "audit_plan": citation_ledger.get("audit_plan"),
        "active_paper_citation_keys": len(paper_keys),
        "active_paper_citation_occurrences": sum(len(items) for items in occurrences_by_key.values()),
        "active_ledger_citation_entries": len(active_citations),
        "active_ledger_citation_keys": len(active_ledger_keys),
        "fitness_status_counts": dict(sorted(status_counts.items())),
        "active_entries_with_locator": len(entries_with_locator),
        "active_entries_with_generic_unaudited_context": len(generic_entries),
        "entries_with_warnings": len(warning_entries),
        "paper_keys_missing_from_active_ledger": sorted(paper_keys - active_ledger_keys),
        "active_ledger_keys_not_in_paper": sorted(active_ledger_keys - paper_keys),
        "citations": sorted(entries, key=lambda entry: (entry.get("bibkeys") or [""], entry.get("citation_id") or "")),
    }


def citation_audit_report():
    print(json.dumps(build_citation_audit_report(), indent=2, sort_keys=True))
    return 0


def citation_review_worksheet_paths() -> list[Path]:
    research_dir = ROOT / "lab/research"
    if not research_dir.exists():
        return []
    return sorted(research_dir.glob("citation-sentence-review-worksheet*.yaml"))


def check_citation_review_worksheet_entry(
    path_label: str,
    entry: dict,
    index: int,
    active_citation_by_key: dict[str, dict],
    locations_by_key: dict[str, list[str]],
) -> int:
    code = 0
    bibkey = entry.get("bibkey")
    if missingish(bibkey):
        return error(f"{path_label} entries[{index}] missing bibkey")
    key = str(bibkey)
    if key not in active_citation_by_key:
        code |= error(f"{path_label} entry {key} is not an active citation-ledger key")
    expected_locations = locations_by_key.get(key, [])
    if not expected_locations:
        code |= error(f"{path_label} entry {key} is not cited in active paper content")
    citation = active_citation_by_key.get(key, {})
    expected_citation_id = item_id(citation, "citation_id", "id", "bibkey")
    citation_id = entry.get("citation_id")
    if expected_citation_id and not missingish(citation_id) and str(citation_id) != expected_citation_id:
        code |= error(f"{path_label} entry {key} citation_id drifts from ledger: {citation_id} != {expected_citation_id}")
    current = entry.get("current_ledger", {}) if isinstance(entry.get("current_ledger"), dict) else {}
    recorded_fitness = current.get("fitness_status")
    ledger_fitness = citation.get("fitness_status")
    if not missingish(recorded_fitness) and str(recorded_fitness) != str(ledger_fitness):
        code |= error(f"{path_label} entry {key} fitness_status drifts from ledger")
    locators = strings(entry.get("all_locators") or entry.get("locators"))
    if sorted(locators) != sorted(expected_locations):
        code |= error(f"{path_label} entry {key} all_locators drift from active paper citations")
    samples = entry.get("local_context_samples", [])
    if samples and not isinstance(samples, list):
        code |= error(f"{path_label} entry {key} local_context_samples must be a list")
    for sample_index, sample in enumerate(samples if isinstance(samples, list) else [], start=1):
        if not isinstance(sample, dict):
            code |= error(f"{path_label} entry {key} local_context_samples[{sample_index}] must be a mapping")
            continue
        sample_path_line = sample.get("path_line")
        if not missingish(sample_path_line) and str(sample_path_line) not in expected_locations:
            code |= error(f"{path_label} entry {key} sample locator not found in active paper citations: {sample_path_line}")
    source_review = entry.get("source_review")
    if not isinstance(source_review, dict):
        code |= error(f"{path_label} entry {key} missing source_review mapping")
        return code
    review_status = str(source_review.get("status") or "").strip().lower()
    if review_status not in CITATION_WORKSHEET_SOURCE_REVIEW_STATUSES:
        allowed = ", ".join(sorted(CITATION_WORKSHEET_SOURCE_REVIEW_STATUSES))
        code |= error(f"{path_label} entry {key} has invalid source_review.status {source_review.get('status')}; allowed: {allowed}")
    decision = str(source_review.get("support_decision") or "needs-review").strip().lower()
    if decision not in CITATION_FITNESS_STATUSES:
        allowed = ", ".join(sorted(CITATION_FITNESS_STATUSES))
        code |= error(f"{path_label} entry {key} has invalid source_review.support_decision {source_review.get('support_decision')}; allowed: {allowed}")
    if review_status == "reviewed":
        if decision not in CITATION_REVIEWED_DECISIONS:
            code |= error(f"{path_label} entry {key} reviewed source_review must end with strong, adequate, weak, or missing-better-source")
        if missingish(source_review.get("source_locator")):
            code |= error(f"{path_label} entry {key} reviewed source_review missing source_locator")
        if missingish(source_review.get("sentence_fit_notes")):
            code |= error(f"{path_label} entry {key} reviewed source_review missing sentence_fit_notes")
    if decision in STRONG_CITATION_FITNESS_STATUSES:
        if missingish(source_review.get("source_locator")) or missingish(source_review.get("sentence_fit_notes")):
            code |= error(f"{path_label} entry {key} strong/adequate source_review requires source_locator and sentence_fit_notes")
    if decision in {"weak", "missing-better-source"} and not meaningful(
        [source_review.get("sentence_fit_notes"), source_review.get("replacement_candidates")]
    ):
        code |= error(f"{path_label} entry {key} {decision} source_review requires notes or replacement_candidates")
    return code


def worksheet_summary_int(path_label: str, summary: dict, field: str) -> tuple[int, int | None]:
    if missingish(summary.get(field)):
        return 0, None
    try:
        return 0, int(summary.get(field))
    except (TypeError, ValueError):
        return error(f"{path_label} summary.{field} must be an integer"), None


def check_citation_review_worksheets():
    paths = citation_review_worksheet_paths()
    if not paths:
        return 0
    code = require(["lab/research/citation-ledger.yaml"])
    if code:
        return code
    citation_ledger = load_doc("lab/research/citation-ledger.yaml")
    citations = citation_ledger.get("citations", [])
    if not isinstance(citations, list):
        citations = []
    active_citation_by_key = {
        key: citation
        for citation in citations
        if isinstance(citation, dict) and active_now(citation)
        for key in citation_bibkeys(citation)
    }
    locations_by_key = {
        key: list(dict.fromkeys(occurrence["path_line"] for occurrence in occurrences))
        for key, occurrences in citation_occurrences_by_key().items()
    }
    for path in paths:
        path_label = rel_posix(path)
        doc = load_doc(path_label)
        if not isinstance(doc, dict):
            code |= error(f"{path_label} must be a mapping")
            continue
        if doc.get("schema_version") != CITATION_WORKSHEET_SCHEMA_VERSION:
            code |= error(f"{path_label} schema_version must be {CITATION_WORKSHEET_SCHEMA_VERSION}")
        entries = doc.get("entries", [])
        if not isinstance(entries, list):
            code |= error(f"{path_label} entries must be a list")
            continue
        seen_keys: set[str] = set()
        for index, entry in enumerate(entries, start=1):
            if not isinstance(entry, dict):
                code |= error(f"{path_label} entries[{index}] must be a mapping")
                continue
            key = str(entry.get("bibkey")) if not missingish(entry.get("bibkey")) else None
            if key:
                if key in seen_keys:
                    code |= error(f"{path_label} duplicate bibkey {key}")
                seen_keys.add(key)
            code |= check_citation_review_worksheet_entry(path_label, entry, index, active_citation_by_key, locations_by_key)
        summary = doc.get("summary", {}) if isinstance(doc.get("summary"), dict) else {}
        count_code, unique_bibkeys = worksheet_summary_int(path_label, summary, "unique_bibkeys")
        code |= count_code
        if unique_bibkeys is not None and unique_bibkeys != len(seen_keys):
            code |= error(f"{path_label} summary.unique_bibkeys does not match entries")
        total_occurrences = sum(len(strings(entry.get("all_locators") or entry.get("locators"))) for entry in entries if isinstance(entry, dict))
        count_code, summary_occurrences = worksheet_summary_int(path_label, summary, "total_paper_occurrences_for_keys")
        code |= count_code
        if summary_occurrences is not None and summary_occurrences != total_occurrences:
            code |= error(f"{path_label} summary.total_paper_occurrences_for_keys does not match entries")
    return code


def extract_macro_names(text: str) -> set[str]:
    names = set()
    pattern = re.compile(r"\\(?:newcommand|renewcommand|providecommand)\s*\{\\([^}]+)\}")
    for match in pattern.finditer(text):
        names.add("\\" + match.group(1))
    return names


def extract_labels(text: str) -> set[str]:
    text = tex_without_comments(text)
    return set(match.group(1).strip() for match in re.finditer(r"\\label\{([^}]+)\}", text))


def extract_refs(text: str) -> set[str]:
    refs = set()
    text = tex_without_comments(text)
    pattern = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref)\{([^}]+)\}")
    for match in pattern.finditer(text):
        for ref in match.group(1).split(","):
            ref = ref.strip()
            if ref:
                refs.add(ref)
    return refs


def extract_tex_command_values(text: str, command: str) -> list[str]:
    values = []
    text = tex_without_comments(text)
    pattern = re.compile(rf"\\{re.escape(command)}\*?")
    for match in pattern.finditer(text):
        index = skip_optional_args(text, match.end())
        index = skip_ws(text, index)
        value, _ = read_balanced_braces(text, index)
        if value is not None:
            values.append(value)
    return values


def extract_tex_command_items(text: str, command: str) -> list[str]:
    items = []
    for value in extract_tex_command_values(text, command):
        for item in value.split(","):
            item = item.strip()
            if item:
                items.append(item)
    return items


def normalize_metadata_text(value) -> str:
    text = str(value or "")
    text = tex_without_comments(text)
    text = re.sub(r"\\['`\"^~=.uvHtcbd]\{?([A-Za-z])\}?", r"\1", text)
    text = re.sub(r"\\[A-Za-z]+\*?(?:\s*\[[^\]]*\])?", " ", text)
    text = text.replace("\\&", "&")
    text = text.replace("\\_", "_")
    text = text.replace("\\%", "%")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^A-Za-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def float_label(label: str) -> bool:
    return label.startswith(FLOAT_LABEL_PREFIXES)


def figure_label(label: str) -> bool:
    return label.startswith(FIGURE_LABEL_PREFIXES)


def table_label(label: str) -> bool:
    return label.startswith(TABLE_LABEL_PREFIXES)


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


def normalize_path_pattern(value: str) -> str:
    pattern = str(value).strip().replace("\\", "/")
    while pattern.startswith("./"):
        pattern = pattern[2:]
    if pattern.endswith("/") and not pattern.endswith("/**"):
        pattern = f"{pattern}**"
    return pattern


def pattern_static_prefix(pattern: str) -> str:
    pattern = normalize_path_pattern(pattern)
    first_glob = len(pattern)
    for char in "*?[":
        index = pattern.find(char)
        if index != -1:
            first_glob = min(first_glob, index)
    return pattern[:first_glob].rstrip("/")


def path_patterns_overlap(candidate: str, forbidden: str) -> bool:
    candidate_pattern = normalize_path_pattern(candidate)
    forbidden_pattern = normalize_path_pattern(forbidden)
    if not candidate_pattern or not forbidden_pattern:
        return False
    if candidate_pattern == forbidden_pattern:
        return True
    if fnmatch.fnmatch(candidate_pattern, forbidden_pattern) or fnmatch.fnmatch(forbidden_pattern, candidate_pattern):
        return True
    candidate_prefix = pattern_static_prefix(candidate_pattern)
    forbidden_prefix = pattern_static_prefix(forbidden_pattern)
    if not candidate_prefix or not forbidden_prefix:
        return False
    return (
        candidate_prefix == forbidden_prefix
        or candidate_prefix.startswith(f"{forbidden_prefix}/")
        or forbidden_prefix.startswith(f"{candidate_prefix}/")
    )


def check_capability_path_contract(capability: dict, cid: str, source: str) -> int:
    code = 0
    forbidden = strings(capability.get("forbidden_paths"))
    if not forbidden:
        return code
    for field in ["outputs", "allowed_paths"]:
        for path in strings(capability.get(field)):
            for pattern in forbidden:
                if path_patterns_overlap(path, pattern):
                    code |= error(f"capability {source} {field} overlaps forbidden_paths: {cid} {path} vs {pattern}")
    return code


def capability_adapter_contract(capability: dict) -> dict:
    contract = capability.get("adapter_contract", {})
    return contract if isinstance(contract, dict) else {}


def check_capability_adapter_contract(capability: dict, cid: str, adapter: str, text: str) -> int:
    code = 0
    contract = capability_adapter_contract(capability)
    required_text = strings(contract.get("required_text"))
    forbidden_text = strings(contract.get("forbidden_text"))
    lowered = text.lower()
    for phrase in required_text:
        if phrase.lower() not in lowered:
            code |= error(f"capability adapter missing required contract text for {cid}: {adapter}: {phrase}")
    for phrase in forbidden_text:
        if phrase.lower() in lowered:
            code |= error(f"capability adapter contains forbidden contract text for {cid}: {adapter}: {phrase}")
    return code


def capability_string_list_field(capability: dict, cid: str, field: str, source: str) -> tuple[int, list[str]]:
    value = capability.get(field)
    if value is None:
        return 0, []
    if not isinstance(value, list):
        return error(f"capability {source} {field} must be a list: {cid}"), []
    code = 0
    values = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or missingish(item):
            code |= error(f"capability {source} {field}[{index}] must be a non-empty string: {cid}")
            continue
        values.append(str(item))
    return code, values


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


def check_release_manifest_contract(manifest: dict) -> int:
    code = 0
    version = manifest.get("manifest_version")
    if version != RELEASE_MANIFEST_VERSION:
        code |= error(
            f"release manifest manifest_version must be {RELEASE_MANIFEST_VERSION}: "
            f"{version or '<missing>'}"
        )
    algorithm = manifest.get("checksum_algorithm")
    if algorithm != CHECKSUM_ALGORITHM:
        code |= error(
            f"release manifest checksum_algorithm must be {CHECKSUM_ALGORITHM}: "
            f"{algorithm or '<missing>'}"
        )
    if "surfaces" in manifest and not isinstance(manifest.get("surfaces"), list):
        code |= error("release manifest surfaces must be a list")
    return code


def manifest_has_synced_release_surfaces(manifest: dict) -> bool:
    surfaces = manifest.get("surfaces", [])
    if not isinstance(surfaces, list):
        return False
    for surface in surfaces:
        if isinstance(surface, dict) and str(surface.get("status", "")).strip().lower() in RELEASE_SYNC_STATUSES:
            return True
    return False


def git_worktree_available() -> bool:
    return git_value("rev-parse", "--is-inside-work-tree") == "true"


def template_skeleton_release(manifest: dict) -> bool:
    if manifest.get("template_skeleton") is not True:
        return False
    ccfa_path = ROOT / "state/ccfa.yaml"
    if not ccfa_path.exists():
        return False
    ccfa = load_doc("state/ccfa.yaml")
    paper = ccfa.get("paper", {}) if isinstance(ccfa.get("paper"), dict) else {}
    return paper.get("slug") == "ccfa-paper-template"


def check_release_source_revision_required(manifest: dict) -> int:
    if not manifest_has_synced_release_surfaces(manifest) or not git_worktree_available():
        return 0
    if template_skeleton_release(manifest):
        return 0
    if meaningful(manifest.get("source_revision")):
        return 0
    return error("release manifest source_revision is required for synced release surfaces in a git worktree")


def normalize_release_source(value) -> str:
    return str(value or "").strip().strip("/")


def check_release_surface_contract(surface_id: str, surface: dict) -> int:
    code = 0
    algorithm = surface.get("checksum_algorithm")
    if algorithm != CHECKSUM_ALGORITHM:
        code |= error(
            f"release surface {surface_id} checksum_algorithm must be {CHECKSUM_ALGORITHM}: "
            f"{algorithm or '<missing>'}"
        )
    source = surface.get("source")
    if normalize_release_source(source) != "paper":
        code |= error(f"release surface {surface_id} source must be paper/: {source or '<missing>'}")
    path_value = str(surface.get("path", "")).strip()
    if surface_id and path_value:
        path = Path(path_value)
        if not path.is_absolute() and ".." not in path.parts and len(path.parts) >= 2 and path.parts[0] == "release":
            expected_path = f"release/{surface_id}"
            if path.as_posix().strip("/") != expected_path:
                code |= error(f"release surface {surface_id} path must be {expected_path}: {path_value}")
    return code


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


def fingerprint_paths(root: Path, paths) -> str:
    entries = sorted(f"{path.relative_to(root).as_posix()}:{sha256_file(path)}" for path in paths)
    return hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()


def kit_fingerprint(raw_template: Path) -> str:
    if raw_template.is_file():
        return fingerprint_paths(raw_template.parent, [raw_template])
    paths = [p for p in raw_template.rglob("*") if p.is_file() and not p.is_symlink()]
    return fingerprint_paths(raw_template, paths)


def paper_source_fingerprint() -> str:
    paths = []
    for item in VENUE_EXPORT_PAPER_ITEMS:
        src = ROOT / "paper" / item
        if not src.exists() or src.is_symlink():
            continue
        if src.is_dir():
            paths.extend(p for p in src.rglob("*") if p.is_file() and not p.is_symlink())
        else:
            paths.append(src)
    compat = ROOT / "paper/style/compat.sty"
    if compat.exists() and not compat.is_symlink():
        paths.append(compat)
    return fingerprint_paths(ROOT, paths)


def normalized_venue_id(ccfa: dict) -> str:
    venue = ccfa.get("venue", {}) if isinstance(ccfa.get("venue"), dict) else {}
    return str(venue.get("id") or "venue").strip().lower() or "venue"


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
    allowed_roots = set(RELEASE_ITEMS) | RELEASE_ROOT_FILES
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        rel_parts = path.relative_to(root).parts
        if rel_parts and rel_parts[0] not in allowed_roots:
            code |= error(
                f"release surface {surface_id} contains non-paper export path: "
                f"{path.relative_to(ROOT).as_posix()}"
            )
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


def flatten_asset_relpath(rel_parts: tuple[str, ...]) -> Path:
    if len(rel_parts) >= 3 and rel_parts[1] == "srcs":
        return Path("srcs", *rel_parts[2:])
    return Path(*rel_parts)


def rewrite_flatten_asset_paths(text: str) -> str:
    text = RELEASE_FLATTEN_SRCS_RE.sub("srcs/", text)
    return RELEASE_FLATTEN_STYLE_RE.sub("{", text)


def compute_flatten_bundle(arxiv_dest: Path, out_dir: Path) -> tuple[str, str | None]:
    """Render a latexpand-flattened, single-entry bundle of an arxiv release surface into out_dir.

    Never touches arxiv_dest; purely optional and skipped (not failed) when latexpand
    or the source main.tex is unavailable, so environments without a TeX toolchain can
    still export releases and get an explicit unverified status instead of a false pass.
    """
    main_tex = arxiv_dest / "main.tex"
    if not main_tex.exists():
        return "skipped-no-main", None
    if not shutil.which("latexpand"):
        return "skipped-no-latexpand", None
    result = subprocess.run(
        ["latexpand", "main.tex"],
        cwd=arxiv_dest,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "error", result.stderr.strip()[:500]
    if "Could not find file" in result.stderr:
        # latexpand exits 0 and leaves the unresolved \input in place on a missing
        # file, only warning on stderr; treat that as a hard failure so a hidden
        # dependency is caught here instead of silently reaching the compile gate.
        return "error", result.stderr.strip()[:500]
    flattened_text = rewrite_flatten_asset_paths(result.stdout)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "main.tex").write_text(flattened_text, encoding="utf-8")
    bib = arxiv_dest / "refs.bib"
    if bib.exists():
        shutil.copy2(bib, out_dir / "refs.bib")
    style_dir = arxiv_dest / "style"
    if style_dir.exists():
        for pattern in RELEASE_FLATTEN_STYLE_PATTERNS:
            for src in sorted(style_dir.glob(pattern)):
                shutil.copy2(src, out_dir / src.name)
    for asset_root_name in RELEASE_FLATTEN_ASSET_DIRS:
        asset_root = arxiv_dest / asset_root_name
        if not asset_root.exists():
            continue
        for src in sorted(asset_root.rglob("*")):
            if not src.is_file() or src.is_symlink():
                continue
            if src.suffix.lower() not in RELEASE_FLATTEN_ASSET_EXTENSIONS:
                continue
            out_rel = flatten_asset_relpath(src.relative_to(arxiv_dest).parts)
            out_path = out_dir / out_rel
            out_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_path)
    return "flattened", None


def flatten_release_surface(surfaces: list[dict]) -> dict | None:
    if not any(str(s.get("id")) == RELEASE_FLATTEN_SOURCE_SURFACE for s in surfaces if isinstance(s, dict)):
        return None
    arxiv_dest = ROOT / "release" / RELEASE_FLATTEN_SOURCE_SURFACE
    flat_dir = ROOT / RELEASE_FLATTEN_PATH
    if flat_dir.exists():
        if flat_dir.is_symlink():
            flat_dir.unlink()
        else:
            shutil.rmtree(flat_dir)
    status, message = compute_flatten_bundle(arxiv_dest, flat_dir)
    record = {
        "id": RELEASE_FLATTEN_ID,
        "path": RELEASE_FLATTEN_PATH,
        "source_surface": RELEASE_FLATTEN_SOURCE_SURFACE,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "status": status,
    }
    if message:
        record["error"] = message
    if status == "flattened":
        record["files"] = collect_release_checksums(flat_dir)
    elif flat_dir.exists():
        shutil.rmtree(flat_dir)
    return record


def check_release_flatten_scan(entry_id: str, root: Path) -> int:
    code = 0
    for candidate in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if candidate.is_symlink():
            code |= error(f"release flatten {entry_id} contains symlink: {candidate.relative_to(ROOT).as_posix()}")
        rel_parts = candidate.relative_to(root).parts
        if any(part in FORBIDDEN_RELEASE_PARTS for part in rel_parts):
            code |= error(f"release flatten {entry_id} leaks harness or metadata path: {candidate.relative_to(ROOT).as_posix()}")
    return code


def verify_flatten_manifest_checksums(entry_id: str, root: Path, entry: dict) -> int:
    files = entry.get("files")
    if not isinstance(files, list):
        return error(f"release flatten {entry_id} missing manifest checksums")
    code = 0
    expected: dict[str, dict] = {}
    for index, item in enumerate(files, start=1):
        if not isinstance(item, dict):
            code |= error(f"release flatten {entry_id} checksum entry {index} is not a mapping")
            continue
        relpath = item.get("relpath")
        sha256 = item.get("sha256")
        size = item.get("size")
        if not isinstance(relpath, str) or not relpath:
            code |= error(f"release flatten {entry_id} checksum entry {index} missing relpath")
            continue
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            code |= error(f"release flatten {entry_id} checksum entry {relpath} has invalid sha256")
        if not isinstance(size, int) or size < 0:
            code |= error(f"release flatten {entry_id} checksum entry {relpath} has invalid size")
        expected[relpath] = {"sha256": sha256, "size": size}
    actual = {item["relpath"]: item for item in collect_release_checksums(root)}
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing:
        code |= error(f"release flatten {entry_id} missing files from manifest: {missing[:10]}")
    if extra:
        code |= error(f"release flatten {entry_id} has files not in manifest: {extra[:10]}")
    for relpath in sorted(set(expected) & set(actual)):
        if expected[relpath]["sha256"] != actual[relpath]["sha256"] or expected[relpath]["size"] != actual[relpath]["size"]:
            code |= error(f"release flatten {entry_id} checksum drift for {relpath}")
    return code


def check_release_flatten_package() -> int:
    manifest = load_doc("release/manifest.yaml")
    if not isinstance(manifest, dict):
        return 0
    entries = manifest.get("flatten", [])
    if not entries:
        return 0
    if not isinstance(entries, list):
        return error("release manifest flatten must be a list")
    code = 0
    seen_ids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            code |= error("release manifest flatten entry must be a mapping")
            continue
        entry_id = str(entry.get("id", "")).strip()
        if not entry_id:
            code |= error("release manifest flatten entry missing id")
            continue
        if entry_id in seen_ids:
            code |= error(f"duplicate release flatten id: {entry_id}")
        seen_ids.add(entry_id)
        path_value = str(entry.get("path", "")).strip()
        path = Path(path_value) if path_value else None
        if not path or path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "release" or len(path.parts) < 2:
            code |= error(f"release flatten {entry_id} has unsafe path: {path_value or '<missing>'}")
            continue
        root = ROOT / path
        if root.is_symlink():
            code |= error(f"release flatten {entry_id} is a symlink: {rel_posix(root)}")
            continue
        status = str(entry.get("status", "")).strip()
        if status not in RELEASE_FLATTEN_STATUSES:
            code |= error(f"release flatten {entry_id} has unknown status: {status or '<missing>'}")
            continue
        if status != "flattened":
            continue
        if not root.exists():
            code |= error(f"missing release flatten output: {path_value}")
            continue
        code |= check_release_flatten_scan(entry_id, root)
        code |= verify_flatten_manifest_checksums(entry_id, root, entry)
    return code


def check_release_flatten_freshness() -> int:
    manifest = load_doc("release/manifest.yaml")
    if not isinstance(manifest, dict):
        return 0
    entries = manifest.get("flatten", [])
    if not entries or not isinstance(entries, list):
        return 0
    code = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", "")).strip()
        if str(entry.get("status", "")).strip() != "flattened":
            continue
        if not shutil.which("latexpand"):
            continue
        path_value = str(entry.get("path", "")).strip()
        root = ROOT / path_value if path_value else None
        source_surface = str(entry.get("source_surface", RELEASE_FLATTEN_SOURCE_SURFACE))
        arxiv_dest = ROOT / "release" / source_surface
        if not root or not root.exists() or not arxiv_dest.exists():
            code |= error(f"release flatten {entry_id} output missing for freshness check")
            continue
        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp) / "flat"
            status, _ = compute_flatten_bundle(arxiv_dest, tmp_dir)
            if status != "flattened":
                code |= error(f"release flatten {entry_id} could not be recomputed for freshness check")
                continue
            current_files = {item["relpath"]: item for item in collect_release_checksums(root)}
            fresh_files = {item["relpath"]: item for item in collect_release_checksums(tmp_dir)}
        if set(current_files) != set(fresh_files):
            code |= error(f"release flatten {entry_id} is stale: file set differs from a fresh latexpand run")
            continue
        for relpath, info in fresh_files.items():
            if current_files[relpath]["sha256"] != info["sha256"]:
                code |= error(f"release flatten {entry_id} is stale: {relpath} differs from a fresh latexpand run")
    return code


ARXIV_PORTABLE_ASSET_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ARXIV_PATH_ARG_RE = re.compile(
    r"\\(input|include|includegraphics(?:\[[^\]]*\])?|bibliography|usepackage|lstinputlisting)"
    r"\s*\{([^{}]*)\}"
)
ARXIV_GRAPHICSPATH_RE = re.compile(r"\\graphicspath\s*\{((?:\{[^{}]*\}\s*)+)\}")
ARXIV_GRAPHICSPATH_ENTRY_RE = re.compile(r"\{([^{}]*)\}")
ARXIV_NONPORTABLE_FONT_RE = re.compile(
    r"\\(?:setmainfont|setsansfont|setmonofont|newfontfamily)\b"
    r"|\\usepackage(?:\[[^\]]*\])?\{fontspec\}"
)


def is_absolute_tex_path(value: str) -> bool:
    value = value.strip()
    return bool(value) and (value.startswith("/") or bool(re.match(r"^[A-Za-z]:[\\/]", value)))


def check_arxiv_portability_text(relpath: str, text: str) -> list[str]:
    problems = []
    for match in ARXIV_NONPORTABLE_FONT_RE.finditer(text):
        problems.append(f"{relpath} uses a non-standard font command requiring system fonts: {match.group(0)}")
    for command, arg in ARXIV_PATH_ARG_RE.findall(text):
        for part in arg.split(","):
            if is_absolute_tex_path(part):
                problems.append(f"{relpath} \\{command} uses an absolute path: {part.strip()}")
    for match in ARXIV_GRAPHICSPATH_RE.finditer(text):
        for entry in ARXIV_GRAPHICSPATH_ENTRY_RE.findall(match.group(1)):
            if is_absolute_tex_path(entry):
                problems.append(f"{relpath} \\graphicspath uses an absolute path: {entry.strip()}")
    return problems


def check_arxiv_portability(surface_id: str = RELEASE_FLATTEN_SOURCE_SURFACE) -> int:
    root = ROOT / "release" / surface_id
    if not root.exists():
        return 0
    code = 0
    for tex_path in sorted(root.rglob("*.tex"), key=lambda item: item.relative_to(root).as_posix()):
        if tex_path.is_symlink():
            continue
        relpath = tex_path.relative_to(root).as_posix()
        for problem in check_arxiv_portability_text(relpath, tex_path.read_text(encoding="utf-8")):
            code |= error(f"arxiv portability: {problem}")
    for asset_dir_name in RELEASE_FLATTEN_ASSET_DIRS:
        asset_dir = root / asset_dir_name
        if not asset_dir.exists():
            continue
        for asset in sorted(asset_dir.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
            if not asset.is_file() or asset.is_symlink():
                continue
            if asset.suffix.lower() in RELEASE_FLATTEN_ASSET_EXTENSIONS and asset.suffix.lower() not in ARXIV_PORTABLE_ASSET_EXTENSIONS:
                code |= error(
                    f"arxiv portability: {asset.relative_to(root).as_posix()} is not a preferred PDF/PNG/JPG asset"
                )
    style_dir = root / "style"
    if style_dir.exists():
        project_macro_names = set(re.findall(r"\\(?:new|renew)command\*?\{?\\([A-Za-z]+)\}?", (root / "macros.tex").read_text(encoding="utf-8"))) if (root / "macros.tex").exists() else set()
        for cls_path in sorted(style_dir.glob("*.cls")):
            if cls_path.is_symlink():
                continue
            class_macro_names = set(re.findall(r"\\(?:new|renew)command\*?\{?\\([A-Za-z]+)\}?", cls_path.read_text(encoding="utf-8")))
            leaked = sorted(project_macro_names & class_macro_names)
            if leaked:
                code |= error(
                    f"arxiv portability: {cls_path.relative_to(root).as_posix()} redefines project macros that belong in macros.tex: {leaked}"
                )
    return code


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


def git_bytes(*args: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def git_branch_names() -> set[str] | None:
    output = git_value("branch", "--format=%(refname:short)")
    if output is None:
        return None
    return {line.strip() for line in output.splitlines() if line.strip()}


def git_worktree_entries() -> dict[Path, str | None] | None:
    output = git_value("worktree", "list", "--porcelain")
    if output is None:
        return None
    entries: dict[Path, str | None] = {}
    current_path: Path | None = None
    current_branch: str | None = None
    for line in output.splitlines() + [""]:
        if not line.strip():
            if current_path is not None:
                entries[current_path] = current_branch
            current_path = None
            current_branch = None
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            current_path = Path(value).expanduser().resolve()
        elif key == "branch":
            current_branch = value.removeprefix("refs/heads/")
    return entries


def worktree_physical_validation_options(doc: dict) -> tuple[bool, bool]:
    value = doc.get("physical_validation", doc.get("physical_validation_enabled", False))
    if isinstance(value, dict):
        enabled = bool(value.get("enabled", value.get("branches", False)))
        require_paths = bool(value.get("require_paths", value.get("paths", False)))
        return enabled, require_paths
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"required", "strict", "true", "yes", "branches"}:
            return True, False
        if normalized in {"paths", "full"}:
            return True, True
        return False, False
    return bool(value), False


def resolve_worktree_path(value) -> Path:
    text = str(value).strip()
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def check_worktree_physical_state(item: dict, branches: set[str], worktree_entries: dict[Path, str | None], *, require_paths: bool) -> int:
    code = 0
    ident = item.get("id", "<missing>")
    branch = str(item.get("branch", "")).strip()
    if missingish(branch):
        code |= error(f"active worktree {ident} missing branch")
    elif branch not in branches:
        code |= error(f"active worktree {ident} branch does not exist: {branch}")

    path_value = None
    for field in ["path", "worktree_path", "root", "cwd"]:
        if not missingish(item.get(field)):
            path_value = item.get(field)
            break
    if missingish(path_value):
        if require_paths:
            code |= error(f"active worktree {ident} missing physical path")
        return code

    path = resolve_worktree_path(path_value)
    if not path.exists():
        code |= error(f"active worktree {ident} physical path does not exist: {path_value}")
        return code
    actual_branch = worktree_entries.get(path)
    if path not in worktree_entries:
        code |= error(f"active worktree {ident} physical path is not in git worktree list: {path_value}")
    elif branch and actual_branch and actual_branch != branch:
        code |= error(f"active worktree {ident} path branch mismatch: expected {branch}, found {actual_branch}")
    return code


def source_revision() -> dict:
    commit = git_value("rev-parse", "--verify", "HEAD")
    tree = git_value("rev-parse", "--verify", "HEAD^{tree}")
    if not commit:
        return {}
    revision = {"treeish": "HEAD", "commit": commit}
    if tree:
        revision["tree"] = tree
    return revision


def current_release_source_files() -> dict[str, Path]:
    files = {}
    for item in RELEASE_ITEMS:
        src = ROOT / "paper" / item
        if not src.exists() or src.is_symlink():
            continue
        if src.is_file():
            files[src.relative_to(ROOT).as_posix()] = src
            continue
        if src.is_dir():
            for path in sorted(src.rglob("*"), key=lambda candidate: candidate.relative_to(src).as_posix()):
                if path.is_file() and not path.is_symlink():
                    files[path.relative_to(ROOT).as_posix()] = path
    return files


def committed_release_source_files(commit: str) -> set[str]:
    paths = set()
    for item in RELEASE_ITEMS:
        output = git_value("ls-tree", "-r", "--name-only", commit, "--", f"paper/{item}")
        if not output:
            continue
        for line in output.splitlines():
            path = line.strip()
            if path:
                paths.add(path)
    return paths


def check_source_revision_matches_release_source(manifest: dict) -> int:
    revision = manifest.get("source_revision", {})
    if not meaningful(revision) or not isinstance(revision, dict):
        return 0
    commit = str(revision.get("commit", "")).strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        return 0
    if git_value("cat-file", "-t", commit) != "commit":
        return 0

    code = 0
    current = current_release_source_files()
    current_paths = set(current)
    committed_paths = committed_release_source_files(commit)
    missing = sorted(current_paths - committed_paths)
    extra = sorted(committed_paths - current_paths)
    if missing:
        code |= error(f"release manifest source_revision missing current paper source files: {missing[:10]}")
    if extra:
        code |= error(f"release manifest source_revision includes absent current paper source files: {extra[:10]}")

    mismatch_count = 0
    for path in sorted(current_paths & committed_paths):
        committed_bytes = git_bytes("show", f"{commit}:{path}")
        if committed_bytes is None:
            if mismatch_count < 10:
                code |= error(f"release manifest source_revision cannot read paper source file: {path}")
            mismatch_count += 1
            continue
        if current[path].read_bytes() != committed_bytes:
            if mismatch_count < 10:
                code |= error(f"release manifest source_revision does not match current paper source: {path}")
            mismatch_count += 1
    if mismatch_count > 10:
        code |= error(f"release manifest source_revision has {mismatch_count - 10} additional paper source mismatches")
    return code


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
    if isinstance(treeish, str) and treeish.strip() and treeish.strip().upper() != "HEAD":
        resolved_treeish = git_value("rev-parse", "--verify", f"{treeish.strip()}^{{commit}}")
        if resolved_treeish and resolved_treeish.lower() != commit:
            code |= error("release manifest source_revision treeish does not resolve to commit")

    expected_tree = git_value("rev-parse", "--verify", f"{commit}^{{tree}}")
    if not re.fullmatch(r"[0-9a-f]{40}", tree):
        code |= error("release manifest source_revision has invalid tree")
        return code
    if git_value("cat-file", "-t", tree) != "tree":
        code |= error(f"release manifest source_revision tree is not present: {tree}")
    elif expected_tree and tree != expected_tree:
        code |= error("release manifest source_revision tree does not match commit")
    code |= check_source_revision_matches_release_source(manifest)
    return code


BRIDGE_CHASSIS_PATH = "state/bridge-chassis.yaml"
BRIDGE_PROFILE = "writing"
CAPABILITY_REGISTRY_PATH = ".agent/capabilities/registry.yaml"
DEFAULT_LATEST_PIN_TOKENS = {
    "*",
    "**",
    "x",
    "x.x",
    "x.x.x",
    "*.*.*",
    "any",
    "latest",
    "current",
    "head",
    "main",
    "master",
    "stable",
    "edge",
    "next",
    "default",
}
# Full anchored semver (per semver.org) so suffix-garbage pins like "1.0.0foo" or
# "abc1" are rejected, not merely accepted by a permissive prefix match.
SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
# Range comparators, longest-first so ">=" is matched before ">".
RANGE_COMPARATORS = (">=", "<=", ">", "<", "=")
# One explicit comparator clause applied to a full X.Y.Z version. Floating forms
# ("^1.0", "~1.2", "1.x", "*", "latest") are intentionally rejected.
RANGE_CLAUSE_RE = re.compile(r"^(?:>=|<=|>|<|=)(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$")


def is_default_latest_pin(value) -> bool:
    """True when a version pin is missing or a floating/default-latest style token."""
    if missingish(value):
        return True
    token = str(value).strip().lower()
    if token in DEFAULT_LATEST_PIN_TOKENS:
        return True
    return "latest" in token


def is_explicit_semver(value) -> bool:
    """True only for a fully anchored X.Y.Z semver (optional prerelease/build)."""
    if is_default_latest_pin(value):
        return False
    return bool(SEMVER_RE.match(str(value).strip()))


def is_explicit_range(value) -> bool:
    """True only for an explicit comparator range, e.g. '>=1.0.0 <2.0.0'."""
    if is_default_latest_pin(value):
        return False
    tokens = str(value).strip().split()
    return bool(tokens) and all(RANGE_CLAUSE_RE.match(token) for token in tokens)


def semver_major(value):
    """Integer MAJOR component of a full semver, or None when unparseable."""
    if is_default_latest_pin(value):
        return None
    match = SEMVER_RE.match(str(value).strip())
    return int(match.group("major")) if match else None


def range_clause_majors(value) -> dict:
    """Map each range comparator to the MAJOR of its version, e.g. {'>=': 1, '<': 2}."""
    majors = {}
    if is_default_latest_pin(value):
        return majors
    for token in str(value).strip().split():
        if not RANGE_CLAUSE_RE.match(token):
            continue
        for comparator in RANGE_COMPARATORS:
            if token.startswith(comparator):
                majors[comparator] = semver_major(token[len(comparator):])
                break
    return majors


def semver_tuple(value):
    """Return (major, minor, patch) ints for a full semver, or None if unparseable.

    Prerelease/build metadata is ignored for range-membership comparison.
    """
    if is_default_latest_pin(value):
        return None
    match = SEMVER_RE.match(str(value).strip())
    if not match:
        return None
    return (int(match.group("major")), int(match.group("minor")), int(match.group("patch")))


def _clause_satisfied(version_tuple, comparator, bound_tuple) -> bool:
    if version_tuple is None or bound_tuple is None:
        return False
    if comparator == ">=":
        return version_tuple >= bound_tuple
    if comparator == "<=":
        return version_tuple <= bound_tuple
    if comparator == ">":
        return version_tuple > bound_tuple
    if comparator == "<":
        return version_tuple < bound_tuple
    if comparator == "=":
        return version_tuple == bound_tuple
    return False


def version_in_range(version, range_str) -> bool:
    """True when a full semver is contained in an explicit comparator range.

    Returns False for unparseable versions/ranges; callers guard with
    is_explicit_semver/is_explicit_range so membership errors are not
    double-reported on inputs already flagged as malformed.
    """
    version_tuple = semver_tuple(version)
    if version_tuple is None or not is_explicit_range(range_str):
        return False
    for token in str(range_str).strip().split():
        if not RANGE_CLAUSE_RE.match(token):
            return False
        for comparator in RANGE_COMPARATORS:
            if token.startswith(comparator):
                bound = semver_tuple(token[len(comparator):])
                if not _clause_satisfied(version_tuple, comparator, bound):
                    return False
                break
    return True


# Placeholder tokens that must not satisfy a "concrete value required" gate.
PLACEHOLDER_TOKENS = {
    "not-vendored",
    "not vendored",
    "none",
    "n/a",
    "na",
    "todo",
    "tbd",
    "pending",
    "placeholder",
    "null",
    "nil",
    "-",
}


def is_placeholder(value) -> bool:
    """True when a value is missing or a placeholder standing in for a real value."""
    if missingish(value):
        return True
    return str(value).strip().lower() in PLACEHOLDER_TOKENS


def check_capability_registry_contract():
    """Registry-level contract/schema versioning and explicit parity/exemptions.

    Rejects a capability registry that omits contract/schema versioning, omits an
    explicit parity policy, or declares a non-required parity without an explicit
    exemption record. Keeps the declarative registry Writing-owned and legible to
    the Bridge chassis compatibility surface.
    """
    if not (ROOT / CAPABILITY_REGISTRY_PATH).exists():
        return error(f"missing {CAPABILITY_REGISTRY_PATH}")
    registry = load_doc(CAPABILITY_REGISTRY_PATH)
    if not isinstance(registry, dict):
        return error("capability registry must be a mapping")
    code = 0
    for field in ["contract_version", "schema_version"]:
        if missingish(registry.get(field)):
            code |= error(f"capability registry missing {field}")
    if missingish(registry.get("parity_policy")):
        code |= error("capability registry missing explicit parity_policy")
    for cap in registry.get("capabilities", []):
        if not isinstance(cap, dict):
            code |= error("capability registry entry must be a mapping")
            continue
        cid = cap.get("id", "<missing>")
        parity = cap.get("parity")
        if missingish(parity):
            code |= error(f"capability missing explicit parity: {cid}")
            continue
        if str(parity).strip().lower() != "required":
            exemptions = cap.get("exceptions")
            has_exemption = isinstance(exemptions, list) and any(meaningful(item) for item in exemptions)
            if not has_exemption:
                code |= error(
                    f"capability parity is not required but declares no explicit exemption: {cid}"
                )
    return code


def check_bridge_chassis_preflight():
    """Writing-side Bridge chassis adoption-readiness preflight.

    This validates the repo's *local* Writing-side pins and self-consistency for
    adopting the research-writing-bridge chassis. It is NOT upstream Bridge
    conformance: the Bridge chassis-spec, protocol schemas, and golden fixtures
    are not vendored or pinned here, and the Bridge issues remain open. Passing
    means the Writing-side adoption surface is internally consistent, not that
    Writing has been validated against a published Bridge contract.

    It enforces that the repo declares profile: writing, pins the chassis/protocol
    contracts with fully explicit semver (no default-latest / floating pins),
    keeps its capability registry versioned and Writing-owned, cross-checks the
    provisional compatibility matrix against the canonical local pins, holds the
    chassis MAJOR baseline steady (so a silent MAJOR bump fails), and classifies
    every registered capability so Writing's paper capabilities are never demanded
    as generic Bridge chassis.
    """
    code = require([BRIDGE_CHASSIS_PATH, "state/ccfa.yaml", CAPABILITY_REGISTRY_PATH])
    if code:
        return code
    chassis = load_doc(BRIDGE_CHASSIS_PATH)
    if not isinstance(chassis, dict):
        return error(f"{BRIDGE_CHASSIS_PATH} must be a mapping")

    profile = chassis.get("profile")
    if missingish(profile):
        code |= error(f"{BRIDGE_CHASSIS_PATH} missing profile")
    elif str(profile).strip() != BRIDGE_PROFILE:
        code |= error(f"{BRIDGE_CHASSIS_PATH} profile must be '{BRIDGE_PROFILE}': {profile}")

    ccfa = load_doc("state/ccfa.yaml")
    if not isinstance(ccfa, dict):
        ccfa = {}
    ccfa_profile = ccfa.get("profile")
    if missingish(ccfa_profile):
        code |= error("state/ccfa.yaml missing profile")
    elif str(ccfa_profile).strip() != BRIDGE_PROFILE:
        code |= error(f"state/ccfa.yaml profile must be '{BRIDGE_PROFILE}': {ccfa_profile}")
    bridge_ptr = ccfa.get("bridge", {}) if isinstance(ccfa.get("bridge"), dict) else {}
    if str(bridge_ptr.get("chassis_pin", "")).strip() != BRIDGE_CHASSIS_PATH:
        code |= error(f"state/ccfa.yaml bridge.chassis_pin must point to {BRIDGE_CHASSIS_PATH}")

    # --- chassis-spec pins + executable MAJOR baseline gate ---
    chassis_spec = chassis.get("chassis", {}) if isinstance(chassis.get("chassis"), dict) else {}
    spec_version = chassis_spec.get("spec_version")
    if missingish(chassis_spec.get("spec")):
        code |= error(f"{BRIDGE_CHASSIS_PATH} chassis.spec missing")
    if not is_explicit_semver(spec_version):
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} chassis.spec_version must be a full explicit semver pin "
            f"(not default/latest/suffixed): {spec_version}"
        )
    spec_range = chassis_spec.get("compatible_range")
    if not is_explicit_range(spec_range):
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} chassis.compatible_range must be an explicit comparator range "
            f"(e.g. '>=1.0.0 <2.0.0'): {spec_range}"
        )
    gate = chassis_spec.get("major_gate", {}) if isinstance(chassis_spec.get("major_gate"), dict) else {}
    for field in ["id", "required_when", "record"]:
        if missingish(gate.get(field)):
            code |= error(
                f"{BRIDGE_CHASSIS_PATH} chassis.major_gate.{field} missing "
                "(chassis MAJOR upgrades must be gated)"
            )
    record_path = gate.get("record")
    if not missingish(record_path) and not (ROOT / str(record_path)).exists():
        code |= error(f"{BRIDGE_CHASSIS_PATH} chassis.major_gate.record does not exist: {record_path}")
    # Executable MAJOR gate: the declared baseline must equal the current spec MAJOR,
    # so bumping spec_version to a new MAJOR fails until approved_major is edited in
    # tandem (a deliberate, reviewable change recorded at major_gate.record).
    approved_major = chassis_spec.get("approved_major")
    current_major = semver_major(spec_version)
    if not isinstance(approved_major, int) or isinstance(approved_major, bool):
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} chassis.approved_major must be an integer baseline for the MAJOR "
            f"gate: {approved_major}"
        )
    elif current_major is not None and current_major != approved_major:
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} chassis.spec_version MAJOR ({current_major}) does not match "
            f"chassis.approved_major ({approved_major}); a chassis MAJOR bump requires updating "
            f"approved_major in tandem and recording the decision at {gate.get('record')}"
        )
    if isinstance(approved_major, int) and not isinstance(approved_major, bool):
        spec_range_majors = range_clause_majors(spec_range)
        lower = spec_range_majors.get(">=", spec_range_majors.get(">"))
        if lower is not None and lower != approved_major:
            code |= error(
                f"{BRIDGE_CHASSIS_PATH} chassis.compatible_range lower bound MAJOR ({lower}) does not "
                f"match chassis.approved_major ({approved_major})"
            )
        upper = spec_range_majors.get("<", spec_range_majors.get("<="))
        if upper is not None and upper not in (approved_major, approved_major + 1):
            code |= error(
                f"{BRIDGE_CHASSIS_PATH} chassis.compatible_range upper bound MAJOR ({upper}) is not "
                f"within the approved MAJOR ({approved_major})"
            )
    if (
        is_explicit_semver(spec_version)
        and is_explicit_range(spec_range)
        and not version_in_range(spec_version, spec_range)
    ):
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} chassis.spec_version {spec_version} is not within "
            f"chassis.compatible_range {spec_range}"
        )

    # --- protocol dual semver pins ---
    protocol = chassis.get("protocol", {}) if isinstance(chassis.get("protocol"), dict) else {}
    for field in ["contract_version", "schema_version"]:
        if not is_explicit_semver(protocol.get(field)):
            code |= error(
                f"{BRIDGE_CHASSIS_PATH} protocol.{field} must be a full explicit semver pin "
                f"(not default/latest/suffixed): {protocol.get(field)}"
            )
    protocol_range = protocol.get("compatible_range")
    if not is_explicit_range(protocol_range):
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} protocol.compatible_range must be an explicit comparator range "
            f"(e.g. '>=1.0.0 <2.0.0'): {protocol_range}"
        )
    for field in ["contract_version", "schema_version"]:
        pin = protocol.get(field)
        if (
            is_explicit_semver(pin)
            and is_explicit_range(protocol_range)
            and not version_in_range(pin, protocol_range)
        ):
            code |= error(
                f"{BRIDGE_CHASSIS_PATH} protocol.{field} {pin} is not within "
                f"protocol.compatible_range {protocol_range}"
            )

    # --- capability registry: versioned, Writing-owned, and pointer-consistent ---
    registry = load_doc(CAPABILITY_REGISTRY_PATH)
    if not isinstance(registry, dict):
        registry = {}
    for field in ["contract_version", "schema_version"]:
        if missingish(registry.get(field)):
            code |= error(
                f"{CAPABILITY_REGISTRY_PATH} missing {field} "
                "(bridge chassis preflight requires a versioned registry)"
            )
    registry_profile = registry.get("profile")
    if missingish(registry_profile) or str(registry_profile).strip() != BRIDGE_PROFILE:
        code |= error(f"{CAPABILITY_REGISTRY_PATH} profile must be '{BRIDGE_PROFILE}': {registry_profile}")
    registry_ownership = registry.get("ownership")
    if missingish(registry_ownership) or str(registry_ownership).strip() != "writing-owned":
        code |= error(f"{CAPABILITY_REGISTRY_PATH} ownership must be 'writing-owned': {registry_ownership}")

    caps = chassis.get("capabilities", {}) if isinstance(chassis.get("capabilities"), dict) else {}
    declared_registry = caps.get("registry")
    if missingish(declared_registry) or str(declared_registry).strip() != CAPABILITY_REGISTRY_PATH:
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} capabilities.registry must equal {CAPABILITY_REGISTRY_PATH}: "
            f"{declared_registry}"
        )
    chassis_contract = caps.get("registry_contract_version")
    registry_contract = registry.get("contract_version")
    if missingish(chassis_contract):
        code |= error(f"{BRIDGE_CHASSIS_PATH} capabilities.registry_contract_version missing")
    elif not missingish(registry_contract) and str(chassis_contract).strip() != str(registry_contract).strip():
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} capabilities.registry_contract_version does not match registry "
            f"contract_version: {chassis_contract} vs {registry_contract}"
        )
    chassis_reg_schema = caps.get("schema_version")
    if not is_explicit_semver(chassis_reg_schema):
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} capabilities.schema_version must be a full explicit semver pin: "
            f"{chassis_reg_schema}"
        )
    registry_schema = registry.get("schema_version")
    if (
        not missingish(chassis_reg_schema)
        and not missingish(registry_schema)
        and str(chassis_reg_schema).strip() != str(registry_schema).strip()
    ):
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} capabilities.schema_version does not match registry schema_version: "
            f"{chassis_reg_schema} vs {registry_schema}"
        )
    if str(caps.get("ownership", "")).strip() != "writing-owned":
        code |= error(f"{BRIDGE_CHASSIS_PATH} capabilities.ownership must be 'writing-owned'")
    if missingish(caps.get("parity_policy")):
        code |= error(f"{BRIDGE_CHASSIS_PATH} capabilities.parity_policy missing")

    # --- provisional compatibility matrix, cross-checked against canonical pins ---
    canonical_rows = {
        "chassis-spec": (spec_version, spec_range),
        "version-pins": (protocol.get("contract_version"), protocol_range),
    }
    matrix = chassis.get("compatibility_matrix")
    if not isinstance(matrix, list) or not matrix:
        code |= error(f"{BRIDGE_CHASSIS_PATH} compatibility_matrix must be a non-empty list")
    else:
        component_counts = {}
        for entry in matrix:
            if isinstance(entry, dict):
                comp = str(entry.get("component", "")).strip()
                if comp:
                    component_counts[comp] = component_counts.get(comp, 0) + 1
        for required in canonical_rows:
            count = component_counts.get(required, 0)
            if count == 0:
                code |= error(
                    f"{BRIDGE_CHASSIS_PATH} compatibility_matrix missing required canonical row: {required}"
                )
            elif count > 1:
                code |= error(
                    f"{BRIDGE_CHASSIS_PATH} compatibility_matrix has duplicate canonical row: "
                    f"{required} (x{count})"
                )
        for index, entry in enumerate(matrix, start=1):
            if not isinstance(entry, dict):
                code |= error(f"{BRIDGE_CHASSIS_PATH} compatibility_matrix[{index}] must be a mapping")
                continue
            component = str(entry.get("component", "")).strip()
            row_pin = entry.get("pinned")
            row_range = entry.get("range")
            if missingish(entry.get("component")):
                code |= error(f"{BRIDGE_CHASSIS_PATH} compatibility_matrix[{index}] missing component")
            if missingish(entry.get("status")):
                code |= error(
                    f"{BRIDGE_CHASSIS_PATH} compatibility_matrix[{index}] missing status "
                    "(rows are provisional adoption targets until Bridge publishes canonical pins)"
                )
            if not is_explicit_semver(row_pin):
                code |= error(
                    f"{BRIDGE_CHASSIS_PATH} compatibility_matrix[{index}] pinned must be a full explicit "
                    f"semver pin (not default/latest/suffixed): {row_pin}"
                )
            if not is_explicit_range(row_range):
                code |= error(
                    f"{BRIDGE_CHASSIS_PATH} compatibility_matrix[{index}] range must be an explicit "
                    f"comparator range: {row_range}"
                )
            if (
                is_explicit_semver(row_pin)
                and is_explicit_range(row_range)
                and not version_in_range(row_pin, row_range)
            ):
                code |= error(
                    f"{BRIDGE_CHASSIS_PATH} compatibility_matrix[{index}] pinned {row_pin} is not within "
                    f"its range {row_range}"
                )
            if component in canonical_rows:
                canon_pin, canon_range = canonical_rows[component]
                if not missingish(canon_pin) and str(entry.get("pinned", "")).strip() != str(canon_pin).strip():
                    code |= error(
                        f"{BRIDGE_CHASSIS_PATH} compatibility_matrix[{index}] '{component}' pinned "
                        f"contradicts canonical pin: {entry.get('pinned')} vs {canon_pin}"
                    )
                if not missingish(canon_range) and str(entry.get("range", "")).strip() != str(canon_range).strip():
                    code |= error(
                        f"{BRIDGE_CHASSIS_PATH} compatibility_matrix[{index}] '{component}' range "
                        f"contradicts canonical range: {entry.get('range')} vs {canon_range}"
                    )

    # --- promotion proposals governance ---
    for index, prop in enumerate(as_list(chassis.get("promotion_proposals")), start=1):
        if not isinstance(prop, dict):
            code |= error(f"{BRIDGE_CHASSIS_PATH} promotion_proposals[{index}] must be a mapping")
            continue
        status = str(prop.get("status", "")).strip().lower()
        if status == "proposed":
            if is_placeholder(prop.get("rfc")):
                code |= error(
                    f"{BRIDGE_CHASSIS_PATH} promotion_proposals[{index}] status 'proposed' requires a "
                    f"concrete rfc (placeholders like 'not-vendored'/'TODO' do not count); downgrade to "
                    f"'candidate' until governance exists"
                )
            concrete_fixtures = [f for f in strings(prop.get("fixtures")) if not is_placeholder(f)]
            if not concrete_fixtures:
                code |= error(
                    f"{BRIDGE_CHASSIS_PATH} promotion_proposals[{index}] status 'proposed' requires "
                    f"concrete fixtures (placeholders like 'not-vendored' do not count); downgrade to "
                    f"'candidate' until governance exists"
                )
            for fixture in concrete_fixtures:
                if not (ROOT / fixture).exists():
                    code |= error(
                        f"{BRIDGE_CHASSIS_PATH} promotion_proposals[{index}] fixture path does not exist: "
                        f"{fixture}"
                    )

    # --- capability classification: Writing owns its whole catalog ---
    registered_ids = {
        str(cap.get("id"))
        for cap in registry.get("capabilities", [])
        if isinstance(cap, dict) and cap.get("id")
    }
    profile_specific = set(strings(chassis.get("profile_specific_capabilities")))
    generic = set(strings(chassis.get("generic_capabilities")))
    overlap = profile_specific & generic
    if overlap:
        code |= error(
            f"{BRIDGE_CHASSIS_PATH} capability is both profile-specific and generic: {sorted(overlap)}"
        )
    for cid in sorted(profile_specific | generic):
        if cid not in registered_ids:
            code |= error(f"{BRIDGE_CHASSIS_PATH} classifies capability not in registry: {cid}")
    for cid in sorted(registered_ids):
        if cid not in profile_specific and cid not in generic:
            code |= error(
                f"{BRIDGE_CHASSIS_PATH} registry capability not classified as profile-specific "
                f"or generic: {cid}"
            )
    return code


def check_capability_parity():
    code = check_capability_registry_contract()
    code |= require([".agent/capabilities/registry.yaml", ".claude/ANATOMY.md", ".agents/ANATOMY.md"])
    registry = load_doc(".agent/capabilities/registry.yaml")
    registered_ids = set()
    for cap in registry.get("capabilities", []):
        cid = cap["id"]
        registered_ids.add(cid)
        source = f".agent/capabilities/{cid}.yaml"
        output_code, outputs = capability_string_list_field(cap, cid, "outputs", "registry")
        validator_code, validators = capability_string_list_field(cap, cid, "validators", "registry")
        code |= output_code | validator_code
        for field in ["allowed_paths", "read_only_paths", "forbidden_paths"]:
            field_code, _ = capability_string_list_field(cap, cid, field, "registry")
            code |= field_code
        adapter_contract = capability_adapter_contract(cap)
        code |= require([
            source,
            cap["claude_adapter"]["skill"],
            cap["codex_adapter"]["workflow"],
        ])
        if cap.get("status") == "active" and not outputs:
            code |= error(f"active capability has no outputs: {cid}")
        if cap.get("status") == "active" and not validators:
            code |= error(f"active capability has no validators: {cid}")
        code |= check_capability_path_contract(cap, cid, "registry")
        if (ROOT / source).exists():
            spec = load_doc(source)
            spec_output_code, spec_outputs = capability_string_list_field(spec, cid, "outputs", "spec")
            spec_validator_code, spec_validators = capability_string_list_field(spec, cid, "validators", "spec")
            code |= spec_output_code | spec_validator_code
            for field in ["allowed_paths", "read_only_paths", "forbidden_paths"]:
                field_code, _ = capability_string_list_field(spec, cid, field, "spec")
                code |= field_code
            spec_adapter_contract = capability_adapter_contract(spec)
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
            if adapter_contract != spec_adapter_contract:
                code |= error(f"capability spec adapter_contract differs from registry: {cid}")
            code |= check_capability_path_contract(spec, cid, "spec")
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
            code |= check_capability_adapter_contract(cap, cid, adapter, text)
    capability_dir = ROOT / ".agent/capabilities"
    for spec_path in sorted(capability_dir.glob("*.yaml")):
        if spec_path.name == "registry.yaml":
            continue
        if spec_path.stem not in registered_ids:
            code |= error(f"capability spec not registered: {rel(spec_path)}")
    declared_claude = {str(cap.get("claude_adapter", {}).get("skill", "")).rstrip("/") for cap in registry.get("capabilities", []) if isinstance(cap, dict)}
    declared_codex = {str(cap.get("codex_adapter", {}).get("workflow", "")) for cap in registry.get("capabilities", []) if isinstance(cap, dict)}
    for skill_dir in sorted((ROOT / ".claude/skills").glob("*")):
        if skill_dir.is_dir() and rel(skill_dir).rstrip("/") not in declared_claude:
            code |= error(f"capability claude adapter not registered: {rel(skill_dir)}")
    for workflow_path in sorted((ROOT / ".agents/workflows").glob("*.md")):
        if rel(workflow_path) not in declared_codex:
            code |= error(f"capability codex adapter not registered: {rel(workflow_path)}")
    for role in registry.get("roles", []):
        code |= require([role["claude_agent"], role["codex_role"]])
    return code


def check_release_package():
    ccfa = load_doc("state/ccfa.yaml")
    manifest = load_doc("release/manifest.yaml")
    code = 0
    if not isinstance(manifest, dict):
        return error("release manifest must be a mapping")
    code |= check_release_manifest_contract(manifest)
    code |= check_release_source_revision_required(manifest)
    expected_surfaces = set(strings(ccfa.get("release", {}).get("surfaces", [])))
    manifest_surfaces = manifest.get("surfaces", [])
    if not isinstance(manifest_surfaces, list):
        manifest_surfaces = []
    seen = set()
    actual_surfaces = set()
    if expected_surfaces and not manifest_surfaces:
        code |= error("release manifest has no surfaces but state/ccfa.yaml declares release surfaces")
    for surface in manifest_surfaces:
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
        code |= check_release_surface_contract(str(surface_id or "<missing>"), surface)
        code |= check_declared_release_surface_status(str(surface_id or "<missing>"), surface, expected_surfaces)
        for field in ["path", "source", "forbidden_paths", "checksum_algorithm"]:
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
    code |= check_release_flatten_package()
    code |= check_arxiv_portability()
    return code


def check_release_freshness():
    manifest = load_doc("release/manifest.yaml")
    code = 0
    expected_surfaces = declared_release_surfaces()
    if isinstance(manifest, dict):
        code |= check_release_source_revision_required(manifest)
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
        for item in RELEASE_ITEMS:
            src = ROOT / "paper" / item
            dest = root / item
            for mismatch in compare_tree(src, dest):
                code |= error(f"release surface {surface_id} is stale: {mismatch}")
    code |= check_release_flatten_freshness()
    return code


def check_worktrees():
    doc = load_doc("state/worktrees.yaml")
    worktrees = doc.get("worktrees", [])
    ids = {item.get("id") for item in worktrees}
    code = 0
    physical_enabled, require_physical_paths = worktree_physical_validation_options(doc)
    branches = None
    worktree_entries = None
    if physical_enabled:
        branches = git_branch_names()
        worktree_entries = git_worktree_entries()
        if branches is None or worktree_entries is None:
            code |= error("state/worktrees.yaml physical_validation requires a git repository")
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
        if (
            physical_enabled
            and active_now(item)
            and branches is not None
            and worktree_entries is not None
        ):
            code |= check_worktree_physical_state(
                item,
                branches,
                worktree_entries,
                require_paths=require_physical_paths,
            )
    return code


def local_existing_path(value) -> Path | None:
    if missingish(value) or external_reference(value):
        return None
    path = ROOT / local_path_part(str(value))
    if path.exists():
        return path
    return None


def normalize_template_use(value) -> str:
    text = str(value or "").strip().strip("{}").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    for suffix in [".sty", ".cls", ".bst", ".tex"]:
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    if text.startswith("paper/"):
        text = text[len("paper/"):]
    return text.strip("/")


def resolve_local_template_use(value, suffix: str) -> Path | None:
    normalized = normalize_template_use(value)
    if not normalized:
        return None
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts:
        return None
    if path.suffix and path.suffix.lower() != suffix:
        return None
    if not path.suffix:
        path = path.with_suffix(suffix)
    paper = (ROOT / "paper").resolve()
    target = (paper / path).resolve()
    try:
        target.relative_to(paper)
    except ValueError:
        return None
    if target.exists() and target.is_file():
        return target
    return None


def local_template_dependencies() -> set[Path]:
    dependencies: set[Path] = set()
    pending_text = [read_paper_tex()]
    command_suffixes = [
        (["usepackage", "RequirePackage"], ".sty"),
        (["documentclass", "LoadClass"], ".cls"),
        (["bibliographystyle"], ".bst"),
    ]
    while pending_text:
        text = pending_text.pop()
        for commands, suffix in command_suffixes:
            for command in commands:
                for item in extract_tex_command_items(text, command):
                    path = resolve_local_template_use(item, suffix)
                    if path is None or path in dependencies:
                        continue
                    dependencies.add(path)
                    if suffix in {".sty", ".cls"}:
                        try:
                            pending_text.append(path.read_text(encoding="utf-8", errors="ignore"))
                        except OSError:
                            continue
    return dependencies


def active_tex_uses_raw_template(raw_path: Path) -> bool:
    suffix = raw_path.suffix.lower()
    if suffix in {".sty", ".cls", ".bst", ".tex"}:
        try:
            raw_resolved = raw_path.resolve()
        except OSError:
            return False
        if suffix == ".tex":
            return raw_resolved in {path.resolve() for path in active_paper_tex_files()}
        return raw_resolved in local_template_dependencies()
    return True


def check_conference_template_binding(template: dict, venue_id, venue_year) -> int:
    raw_path = local_existing_path(template.get("raw_template"))
    if raw_path is None or not raw_path.is_file():
        return 0

    code = 0
    raw_rel = raw_path.relative_to(ROOT).as_posix()
    try:
        raw_text = raw_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        raw_text = ""
    binding_text = normalize_metadata_text(f"{raw_rel}\n{raw_text}")
    venue = normalize_metadata_text(venue_id)
    if venue and venue not in binding_text:
        code |= error(f"conference template raw_template does not mention declared venue: {venue_id}")

    year = str(venue_year or "").strip()
    path_years = set(re.findall(r"(?:19|20)\d{2}", raw_path.name))
    if year and path_years and year not in path_years:
        code |= error(f"conference template raw_template filename year does not match declared year: {venue_year}")
    if not active_tex_uses_raw_template(raw_path):
        code |= error(f"conference template raw_template is not used by active paper tex: {raw_rel}")
    return code


def check_conference_template():
    ccfa = load_doc("state/ccfa.yaml")
    template = load_doc("state/conference-template.yaml")
    code = 0
    venue = ccfa.get("venue", {}) if isinstance(ccfa.get("venue"), dict) else {}
    venue_id = venue.get("id")
    venue_year = venue.get("year")
    if template.get("venue") != venue_id:
        code |= error("conference template venue does not match state/ccfa.yaml")
    if template.get("year") != venue_year:
        code |= error("conference template year does not match state/ccfa.yaml")
    code |= check_conference_template_binding(template, venue_id, venue_year)
    compat_shim = template.get("compat_shim")
    if not missingish(compat_shim) and not path_exists_or_external(compat_shim):
        code |= error(f"conference template compat_shim not found: {compat_shim}")
    if str(template.get("status", "")).lower() == "verified":
        for field in ["raw_template", "normalized_template", "delta", "hash", "source", "downloaded_at", "human_verified_at"]:
            if missingish(template.get(field)):
                code |= error(f"verified conference template missing {field}")
        for field in ["raw_template", "normalized_template", "delta"]:
            if not path_exists_or_external(template.get(field)):
                code |= error(f"verified conference template path/source not found: {field}={template.get(field)}")
    code |= check_realkit_verification()
    return code


def find_realkit_receipt(template: dict, venue_id, venue_year, mode) -> dict | None:
    receipts = template.get("realkit_receipts")
    if not isinstance(receipts, list):
        return None
    for entry in receipts:
        if not isinstance(entry, dict):
            continue
        if (
            str(entry.get("venue")) == str(venue_id)
            and str(entry.get("year")) == str(venue_year)
            and entry.get("mode") == mode
        ):
            return entry
    return None


def check_realkit_verification() -> int:
    ccfa = load_doc("state/ccfa.yaml")
    template = load_doc("state/conference-template.yaml")
    if not paper_looks_populated():
        return 0
    raw_template_value = template.get("raw_template")
    if missingish(raw_template_value) or external_reference(raw_template_value):
        return 0

    venue_id = normalized_venue_id(ccfa)
    venue = ccfa.get("venue", {}) if isinstance(ccfa.get("venue"), dict) else {}
    venue_year = venue.get("year")
    team = ccfa.get("team", {}) if isinstance(ccfa.get("team"), dict) else {}
    mode = "anonymous" if anonymous_mode_enabled(team) else "camera-ready"

    entry = find_realkit_receipt(template, venue_id, venue_year, mode)
    if entry is None:
        return error(
            f"no real-kit compile receipt recorded for venue={venue_id} year={venue_year} mode={mode}; "
            f"run scripts/export-venue-template.sh --mode {mode} against the configured raw_template "
            "to compile against the real kit and record one"
        )

    code = 0
    if str(entry.get("status", "")).lower() != "verified":
        code |= error(
            f"real-kit compile receipt for venue={venue_id} mode={mode} has status != verified: {entry.get('status')}"
        )
    expected_source = f"sha256:{paper_source_fingerprint()}"
    if entry.get("source_fingerprint") != expected_source:
        code |= error(
            f"real-kit compile receipt for venue={venue_id} mode={mode} is stale: "
            "compat.sty or paper/ sources changed since the last verified real-kit compile"
        )
    raw_path = local_existing_path(raw_template_value)
    if raw_path is not None:
        expected_kit = f"sha256:{kit_fingerprint(raw_path)}"
        if entry.get("kit_checksum") != expected_kit:
            code |= error(
                f"real-kit compile receipt for venue={venue_id} mode={mode} is stale: "
                "the configured raw_template kit contents changed since the last verified real-kit compile"
            )
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


def check_nn_name_wrappers(dir_path: Path, dir_rel: str) -> int:
    code = 0
    if not dir_path.exists():
        return code
    for path in sorted(dir_path.glob("*.tex")):
        if not NN_NAME_RE.match(path.stem):
            code |= error(
                f"{dir_rel}/{path.name} does not match the NN_name convention "
                "(two-digit prefix, 0=body/1=appendix, then lowercase snake_case name)"
            )
    return code


def check_section_naming_and_order() -> int:
    code = check_nn_name_wrappers(ROOT / "paper/sections", "paper/sections")
    main_path = ROOT / "paper/main.tex"
    if not main_path.exists():
        return code
    text = main_path.read_text(encoding="utf-8")
    appendix_match = re.search(r"\\appendix\b", text)
    appendix_pos = appendix_match.start() if appendix_match else None
    body_stems: list[str] = []
    appendix_stems: list[str] = []
    for match in re.finditer(r"\\input\{sections/([^}]+)\}", text):
        stem = match.group(1)
        if not NN_NAME_RE.match(stem):
            code |= error(f"paper/main.tex inputs sections/{stem} which does not match the NN_name convention")
            continue
        is_body = appendix_pos is None or match.start() < appendix_pos
        expected_prefix = "0" if is_body else "1"
        if stem[0] != expected_prefix:
            side = "before" if is_body else "after"
            code |= error(
                f"paper/main.tex inputs sections/{stem} {side} \\appendix but its prefix is not {expected_prefix}"
            )
        (body_stems if is_body else appendix_stems).append(stem)
    for group in (body_stems, appendix_stems):
        if group != sorted(group):
            code |= error(f"paper/main.tex \\input order for sections is not ascending: {group}")
    return code


def check_figure_table_wrapper_naming() -> int:
    code = check_nn_name_wrappers(ROOT / "paper/figures", "paper/figures")
    code |= check_nn_name_wrappers(ROOT / "paper/tables", "paper/tables")
    figures_dir = ROOT / "paper/figures"
    srcs_dir = figures_dir / "srcs"
    if figures_dir.exists():
        for path in sorted(figures_dir.glob("*.tex")):
            stem = path.stem
            if not NN_NAME_RE.match(stem):
                continue
            assets = sorted(srcs_dir.glob(f"{stem}.*")) if srcs_dir.exists() else []
            if not any(asset.suffix.lower() in FIGURE_ASSET_EXTENSIONS for asset in assets):
                code |= error(
                    f"paper/figures/{path.name} has no matching asset in "
                    f"paper/figures/srcs/{stem}.<pdf|png|jpg|jpeg>"
                )
    if srcs_dir.exists():
        for asset in sorted(srcs_dir.glob("*")):
            if asset.is_dir() or asset.suffix.lower() not in FIGURE_ASSET_EXTENSIONS:
                continue
            wrapper = figures_dir / f"{asset.stem}.tex"
            if not wrapper.exists():
                code |= error(
                    f"paper/figures/srcs/{asset.name} has no matching wrapper paper/figures/{asset.stem}.tex"
                )
    return code


def check_anatomy_drift():
    code = require([
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
    code |= check_section_naming_and_order()
    return code


def check_paper_surface():
    code = require(REQUIRED_PAPER_SURFACE)
    main = ROOT / "paper/main.tex"
    if not main.exists():
        return code
    text = main.read_text(encoding="utf-8")
    for section in SECTION_INPUT_FILES:
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


def mapped_float_for_index_item(item: dict, by_float_id: dict, by_label: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    float_id = item.get("float_id")
    if not missingish(float_id):
        mapped = by_float_id.get(str(float_id))
        if mapped is not None:
            return mapped
    label = item.get("label")
    if not missingish(label):
        return by_label.get(str(label))
    return None


def label_for_index_item(item: dict, by_float_id: dict, by_label: dict) -> str | None:
    if not isinstance(item, dict):
        return None
    label = item.get("label")
    if missingish(label):
        mapped_float = mapped_float_for_index_item(item, by_float_id, by_label)
        if isinstance(mapped_float, dict):
            label = mapped_float.get("label")
    if missingish(label):
        return None
    return str(label)


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
    text = tex_without_comments(text)
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


def figure_block_declared_asset_paths(
    block: str,
    figures: list[dict],
    active_by_float_id: dict,
    active_by_label: dict,
) -> list[tuple[str, str, set[str]]]:
    labels = extract_labels(block)
    declarations = []
    for label in labels:
        mapped_float = active_by_label.get(label)
        if isinstance(mapped_float, dict):
            declarations.append(mapped_float)
    for figure in figures:
        if not isinstance(figure, dict) or not active_now(figure):
            continue
        label = label_for_index_item(figure, active_by_float_id, active_by_label)
        if label not in labels:
            continue
        declarations.append(figure)
        mapped_float = mapped_float_for_index_item(figure, active_by_float_id, active_by_label)
        if isinstance(mapped_float, dict):
            declarations.append(mapped_float)
    return declared_asset_paths(*declarations)


def check_figure_asset_binding(
    item: dict,
    mapped_float: dict | None,
    label: str,
    ident: str,
    text: str,
    figures: list[dict] | None = None,
    active_by_float_id: dict | None = None,
    active_by_label: dict | None = None,
) -> int:
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
    declared = declared_asset_paths(item, mapped_float)
    for field, value, variants in declared:
        if not variants & actual_variants:
            sample = ", ".join(actual_paths[:5])
            code |= error(
                f"figure {ident} includegraphics asset mismatch for {field}: "
                f"expected {value}; found {sample}"
            )
    block_declared = declared
    if figures is not None and active_by_float_id is not None and active_by_label is not None:
        block_declared = figure_block_declared_asset_paths(block, figures, active_by_float_id, active_by_label)
    declared_variant_sets = [variants for _field, _value, variants in block_declared]
    for path in actual_paths:
        variants = asset_path_variants(path)
        if not variants:
            continue
        if not any(variants & declared_variants for declared_variants in declared_variant_sets):
            code |= error(f"figure {ident} includegraphics asset not registered: {path}")
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


def strip_math_delimiters(value: str) -> str:
    text = str(value).strip()
    wrappers = [("$", "$"), ("\\(", "\\)"), ("\\[", "\\]")]
    for prefix, suffix in wrappers:
        if text.startswith(prefix) and text.endswith(suffix) and len(text) > len(prefix) + len(suffix):
            return text[len(prefix) : -len(suffix)].strip()
    return text


def strip_math_scripts(value: str) -> str:
    text = str(value)
    output = []
    index = 0
    while index < len(text):
        char = text[index]
        if char in {"_", "^"}:
            index += 1
            if index < len(text) and text[index] == "{":
                depth = 1
                index += 1
                while index < len(text) and depth:
                    if text[index] == "{":
                        depth += 1
                    elif text[index] == "}":
                        depth -= 1
                    index += 1
                continue
            if index < len(text) and text[index] == "\\":
                index += 1
                while index < len(text) and text[index].isalpha():
                    index += 1
                continue
            index += 1
            continue
        output.append(char)
        index += 1
    return "".join(output)


def normalize_math_expression(value: str) -> str:
    text = strip_math_delimiters(value)
    text = text.replace("\\left", "").replace("\\right", "")
    return re.sub(r"\s+", "", text).strip()


def notation_symbol_keys(symbol: str) -> set[str]:
    normalized = normalize_math_expression(symbol)
    if not normalized:
        return set()
    keys = {normalized}
    without_scripts = strip_math_scripts(normalized)
    if without_scripts:
        keys.add(without_scripts)
    return keys


def registered_notation_keys(symbols: list[dict]) -> set[str]:
    keys = set()
    for item in symbols:
        if not isinstance(item, dict) or not active_now(item):
            continue
        symbol = item.get("symbol") or item.get("latex")
        if missingish(symbol):
            continue
        for variant in notation_symbol_variants(str(symbol)):
            keys.update(notation_symbol_keys(variant))
    return keys


def inline_math_spans_with_context(text: str) -> list[tuple[str, str]]:
    spans = []
    pattern = re.compile(r"(?<!\\)\$(?!\$)(.+?)(?<!\\)\$|\\\((.+?)\\\)")
    for line in text.splitlines():
        stripped = strip_tex_comment(line)
        if not DEFINITIONAL_NOTATION_CONTEXT_RE.search(stripped):
            continue
        for match in pattern.finditer(stripped):
            expression = next(group for group in match.groups() if group is not None)
            spans.append((expression.strip(), stripped.strip()))
    return spans


def notation_expression_requires_registration(expression: str) -> bool:
    normalized = normalize_math_expression(expression)
    if not normalized:
        return False
    if not re.search(r"[A-Za-z\\]", normalized):
        return False
    return bool(NOTATION_COMMAND_RE.search(normalized))


def check_unregistered_definitional_notation(symbols: list[dict], paper_content: str) -> int:
    code = 0
    registered = registered_notation_keys(symbols)
    for expression, _context in inline_math_spans_with_context(paper_content):
        if not notation_expression_requires_registration(expression):
            continue
        expression_keys = notation_symbol_keys(expression)
        if expression_keys and not expression_keys & registered:
            code |= error(f"active notation use is not registered: {expression}")
    return code


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


def numeric_values_compatible(left_values: list[str], right_values: list[str]) -> bool:
    for left in left_values:
        left_equivalents = numeric_value_equivalents(left)
        for right in right_values:
            if left_equivalents & numeric_value_equivalents(right):
                return True
    return False


def check_number_value_consistency(numeric_id: str, number: dict) -> int:
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
    if direct_values and display_values and not numeric_values_compatible(direct_values, display_values):
        return error(f"number {numeric_id} value contradicts display value")
    return 0


def numeric_value_equivalents(value) -> set[str]:
    normalized = normalize_numeric_value(value)
    values = {normalized} if normalized else set()
    if normalized.endswith("%"):
        values.add(normalized[:-1])
    currency_stripped = re.sub(r"^(?:usd|us\$|\$)", "", normalized)
    currency_stripped = re.sub(r"(?:usd)$", "", currency_stripped)
    if currency_stripped and currency_stripped != normalized:
        values.add(currency_stripped)
    return values


def claim_statement_text(claim: dict) -> str:
    values = []
    for field in CLAIM_STATEMENT_FIELDS:
        value = claim.get(field)
        if not missingish(value):
            values.append(str(value))
    return "\n".join(values)


def claim_numeric_literals(claim: dict) -> list[str]:
    text = claim_statement_text(claim)
    return [match.group(0).strip() for match in NUMERIC_LITERAL_RE.finditer(text) if match.group(0).strip()]


def active_claim_ids(claims: list[dict]) -> set[str]:
    return {
        claim_id
        for claim in claims
        if (claim_id := item_id(claim, "claim_id", "id")) and active_now(claim)
    }


def check_claim_numeric_literal_bindings(claims: list[dict], number_by_id: dict[str, dict]) -> int:
    code = 0
    numbers_by_claim_id: dict[str, set[str]] = {}
    for numeric_id, number in number_by_id.items():
        if not is_verified(number):
            continue
        for claim_id in strings(number.get("claim_ids")):
            numbers_by_claim_id.setdefault(claim_id, set()).add(numeric_id)

    for claim in claims:
        claim_id = item_id(claim, "claim_id", "id")
        if not claim_id or not is_active(claim) or claim_strength(claim) not in {"core", "strong"}:
            continue
        literals = claim_numeric_literals(claim)
        if not literals:
            continue
        explicit_numeric_ids = set(strings(claim.get("numeric_ids")))
        for numeric_id in explicit_numeric_ids:
            number = number_by_id.get(numeric_id)
            if not number:
                continue
            number_claim_ids = set(strings(number.get("claim_ids")))
            if number_claim_ids and claim_id not in number_claim_ids:
                code |= error(f"claim {claim_id} numeric_id {numeric_id} is not reciprocated by number claim_ids")
        linked_numeric_ids = explicit_numeric_ids or numbers_by_claim_id.get(claim_id, set())
        if not linked_numeric_ids:
            sample = ", ".join(literals[:5])
            code |= error(f"claim {claim_id} has numeric literal without numeric binding: {sample}")
            continue
        supported_values: set[str] = set()
        for numeric_id in linked_numeric_ids:
            number = number_by_id.get(numeric_id)
            if not number or not is_verified(number):
                continue
            for value in registered_number_values(number):
                supported_values.update(numeric_value_equivalents(value))
        for literal in literals:
            literal_values = numeric_value_equivalents(literal)
            if supported_values and literal_values & supported_values:
                continue
            code |= error(f"claim {claim_id} numeric literal not backed by linked verified numbers: {literal}")
    return code


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


def collect_evidence_matrix_relationships() -> dict[tuple[str, str], set[str]]:
    relationships: dict[tuple[str, str], set[str]] = {}
    for row in read_csv_rows("state/evidence-matrix.csv"):
        claim_id = str(row.get("claim_id", "")).strip()
        evidence_id = str(row.get("evidence_id", "")).strip()
        relationship = normalized_text(row.get("relationship", ""))
        if missingish(claim_id) or missingish(evidence_id) or missingish(relationship):
            continue
        if relationship not in ALLOWED_EVIDENCE_RELATIONSHIPS or not matrix_row_active(row):
            continue
        relationships.setdefault((claim_id, evidence_id), set()).add(relationship)
    return relationships


def evidence_supports_result_claim(
    claim_id: str,
    evidence_id: str,
    claim_refs_by_id: dict[str, set[str]],
    _evidence_supports_by_id: dict[str, set[str]],
    matrix_relationships: dict[tuple[str, str], set[str]],
) -> bool:
    relationships = matrix_relationships.get((claim_id, evidence_id), set())
    if relationships:
        return bool(relationships & SUPPORT_RELATIONSHIPS) and not bool(relationships & CONTRADICT_RELATIONSHIPS)
    return evidence_id in claim_refs_by_id.get(claim_id, set())


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


def result_status_class(result: dict) -> str:
    if is_verified(result):
        return "verified"
    if is_planned(result):
        return "planned"
    if not is_active(result):
        return "inactive"
    status = normalized_text(result.get("status", ""))
    return status or "active"


def compare_declared_result_set(result_id: str, label: str, status_values: set[str], index_values: set[str]) -> int:
    if not status_values or not index_values or status_values == index_values:
        return 0
    return error(
        f"result {result_id} {label} differ between result-status and result-index: "
        f"state {sorted(status_values)}, index {sorted(index_values)}"
    )


def validate_result_ledger_parity(result: dict, index_result: dict | None) -> int:
    if not index_result:
        return 0
    result_id = item_id(result, "result_id", "id")
    if not result_id:
        return 0
    code = 0
    if has_value(result.get("status")) and has_value(index_result.get("status")):
        status_class = result_status_class(result)
        index_status_class = result_status_class(index_result)
        if status_class != index_status_class:
            code |= error(
                f"result {result_id} status differs between result-status and result-index: "
                f"{status_class} != {index_status_class}"
            )
    if "claims_supported" in result and "claims_supported" in index_result:
        code |= compare_declared_result_set(
            result_id,
            "claims_supported",
            set(strings(result.get("claims_supported"))),
            set(strings(index_result.get("claims_supported"))),
        )
    if any(field in result for field in ["evidence_ids", "evidence_id", "evidence"]) and any(
        field in index_result for field in ["evidence_ids", "evidence_id", "evidence"]
    ):
        code |= compare_declared_result_set(
            result_id,
            "evidence_ids",
            set(evidence_refs(result)),
            set(evidence_refs(index_result)),
        )
    result_numeric, result_has_numeric, _ = result_numeric_refs(result)
    index_numeric, index_has_numeric, _ = result_numeric_refs(index_result)
    if result_has_numeric and index_has_numeric:
        code |= compare_declared_result_set(result_id, "numeric_ids", set(result_numeric), set(index_numeric))
    result_anchors = set(path_anchor_values(result))
    index_anchors = set(path_anchor_values(index_result))
    code |= compare_declared_result_set(result_id, "source/artifacts", result_anchors, index_anchors)
    return code


def validate_result_claim_numeric_alignment(result: dict, number_by_id: dict[str, dict]) -> int:
    result_id = item_id(result, "result_id", "id")
    if not result_id or not is_verified(result):
        return 0
    refs, _field_present, _missing_entry_id = result_numeric_refs(result)
    if not refs:
        return 0
    result_claim_ids = set(strings(result.get("claims_supported")))
    if not result_claim_ids:
        return 0
    code = 0
    for numeric_id in refs:
        number = number_by_id.get(numeric_id)
        if not number:
            continue
        number_claim_ids = set(strings(number.get("claim_ids")))
        if number_claim_ids and result_claim_ids.isdisjoint(number_claim_ids):
            code |= error(f"result {result_id} claim bindings do not match numeric {numeric_id} claim_ids")
        number_result_ids = set(result_refs(number))
        if result_id not in number_result_ids:
            code |= error(f"result {result_id} numeric {numeric_id} is not reciprocated by number result_id")
    return code


def validate_verified_result_active_claim_bindings(
    result: dict,
    claim_ids: set[str],
    active_claim_id_set: set[str],
    *,
    verified: bool | None = None,
) -> int:
    result_id = item_id(result, "result_id", "id")
    if not result_id:
        return 0
    if verified is None:
        verified = is_verified(result)
    if not verified:
        return 0
    code = 0
    for claim_id in strings(result.get("claims_supported")):
        if claim_ids and claim_id not in claim_ids:
            code |= error(f"result {result_id} supports unknown claim {claim_id}")
        elif claim_ids and claim_id not in active_claim_id_set:
            code |= error(f"verified result {result_id} supports inactive claim {claim_id}")
    return code


def validate_result_evidence_claim_alignment(
    result: dict,
    claim_ids: set[str],
    evidence_by_id: dict[str, dict],
    claim_refs_by_id: dict[str, set[str]],
    evidence_supports_by_id: dict[str, set[str]],
    matrix_relationships: dict[tuple[str, str], set[str]],
    *,
    verified: bool | None = None,
    reported: set[tuple[str, str, tuple[str, ...]]] | None = None,
) -> int:
    result_id = item_id(result, "result_id", "id")
    if not result_id:
        return 0
    if verified is None:
        verified = is_verified(result)
    if not verified:
        return 0
    result_claim_ids = set(strings(result.get("claims_supported")))
    result_evidence_ids = set(evidence_refs(result))
    if not result_claim_ids or not result_evidence_ids:
        return 0

    code = 0
    known_evidence_ids = []
    for evidence_id in sorted(result_evidence_ids):
        if evidence_id not in evidence_by_id:
            code |= error(f"result {result_id} references unknown evidence {evidence_id}")
        else:
            known_evidence_ids.append(evidence_id)
    if not known_evidence_ids:
        return code

    for claim_id in sorted(result_claim_ids):
        if claim_ids and claim_id not in claim_ids:
            continue
        supporting_evidence_ids = [
            evidence_id
            for evidence_id in known_evidence_ids
            if evidence_supports_result_claim(
                claim_id,
                evidence_id,
                claim_refs_by_id,
                evidence_supports_by_id,
                matrix_relationships,
            )
        ]
        if supporting_evidence_ids and any(
            evidence_can_support_verified_result(evidence_by_id[evidence_id])
            for evidence_id in supporting_evidence_ids
        ):
            continue
        report_key = (result_id, claim_id, tuple(known_evidence_ids))
        if reported is not None:
            if report_key in reported:
                continue
            reported.add(report_key)
        if supporting_evidence_ids:
            code |= error(
                f"result {result_id} claim {claim_id} lacks verified direct evidence among result evidence_ids: "
                f"{supporting_evidence_ids}"
            )
        else:
            code |= error(
                f"result {result_id} claim {claim_id} is not supported by result evidence_ids: {known_evidence_ids}"
            )
    return code


VALID_EXCEPTION_MATCH_SCOPES = {"literal", "context", "literal_or_context"}
NUMERIC_EXCEPTION_REPORT_SAMPLE_LIMIT = 5


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


def numeric_exception_report_entry(index: int, item, literals: list[tuple[Path, int, str, str]]) -> dict:
    entry = {
        "index": index,
        "id": None,
        "reason": None,
        "match_scope": "literal",
        "pattern": None,
        "path_pattern_present": False,
        "path_pattern": None,
        "match_count": 0,
        "path_counts": {},
        "sample_matches": [],
        "warnings": [],
    }
    if not isinstance(item, dict):
        entry["warnings"].append("entry is not a mapping")
        return entry

    entry["id"] = item_id(item, "id", "exception_id")
    if entry["id"] is None:
        entry["warnings"].append("missing id")

    pattern = item.get("pattern")
    reason = item.get("reason")
    if missingish(pattern):
        entry["warnings"].append("missing pattern")
    else:
        entry["pattern"] = str(pattern)
    if missingish(reason):
        entry["warnings"].append("missing reason")
    else:
        entry["reason"] = str(reason)

    match_scope = normalize_exception_match_scope(item.get("match_scope"))
    entry["match_scope"] = match_scope
    if match_scope not in VALID_EXCEPTION_MATCH_SCOPES:
        entry["warnings"].append(
            f"invalid match_scope {item.get('match_scope')}; expected literal, context, or literal_or_context"
        )

    entry["path_pattern_present"] = "path_pattern" in item
    path_pattern = item.get("path_pattern")
    if entry["path_pattern_present"] and path_pattern is not None:
        entry["path_pattern"] = str(path_pattern)
    if not entry["path_pattern_present"] or missingish(path_pattern):
        entry["warnings"].append("missing path_pattern")

    if missingish(pattern) or missingish(reason) or match_scope not in VALID_EXCEPTION_MATCH_SCOPES:
        return entry

    try:
        compiled_pattern = re.compile(str(pattern))
    except re.error as exc:
        entry["warnings"].append(f"invalid regex: {exc}")
        return entry

    compiled_path_pattern = None
    if not missingish(path_pattern):
        try:
            compiled_path_pattern = re.compile(str(path_pattern))
        except re.error as exc:
            entry["warnings"].append(f"invalid path_pattern regex: {exc}")
            return entry

    exception = {
        "pattern": compiled_pattern,
        "reason": str(reason),
        "match_scope": match_scope,
        "path_pattern": compiled_path_pattern,
    }
    path_counts: dict[str, int] = {}
    samples = []
    for path, line_no, literal, context in literals:
        if not exception_matches(exception, path, literal, context):
            continue
        path_key = rel_posix(path)
        path_counts[path_key] = path_counts.get(path_key, 0) + 1
        if len(samples) < NUMERIC_EXCEPTION_REPORT_SAMPLE_LIMIT:
            samples.append(
                {
                    "path": path_key,
                    "line": line_no,
                    "path_line": f"{path_key}:{line_no}",
                    "literal": literal,
                    "context": context,
                }
            )

    entry["match_count"] = sum(path_counts.values())
    entry["path_counts"] = dict(sorted(path_counts.items()))
    entry["sample_matches"] = samples
    return entry


def build_numeric_exception_report() -> dict:
    exceptions = doc_items("state/numbers/exceptions.yaml", "exceptions")
    literals = list(iter_paper_numeric_literals())
    return {
        "report_version": "numeric-exception-report-v1",
        "exception_file": "state/numbers/exceptions.yaml",
        "sample_limit": NUMERIC_EXCEPTION_REPORT_SAMPLE_LIMIT,
        "numeric_literal_count": len(literals),
        "exceptions": [
            numeric_exception_report_entry(index, item, literals)
            for index, item in enumerate(exceptions, start=1)
        ],
    }


def numeric_exception_report():
    print(json.dumps(build_numeric_exception_report(), indent=2, sort_keys=True))
    return 0


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
    code = require([
        "state/result-status.yaml",
        "lab/artifacts/result-index.yaml",
        "state/claim-evidence-map.yaml",
        "lab/research/evidence.yaml",
        "state/evidence-matrix.csv",
    ])
    if code:
        return code
    status_results = doc_items("state/result-status.yaml", "results")
    index_results = doc_items("lab/artifacts/result-index.yaml", "results")
    claims = doc_items("state/claim-evidence-map.yaml", "claims")
    evidence = doc_items("lab/research/evidence.yaml", "evidence")
    numbers = load_numeric_numbers()

    code |= collect_ids(status_results, ["result_id", "id"], "state/result-status.yaml results", required=False)[0]
    index_code, index_ids = collect_ids(index_results, ["result_id", "id"], "lab/artifacts/result-index.yaml results", required=False)
    code |= index_code
    claim_ids = collect_ids(claims, ["claim_id", "id"], "claims", required=False)[1]
    active_claim_id_set = active_claim_ids(claims)
    evidence_code, evidence_ids = collect_ids(evidence, ["evidence_id", "id"], "evidence", required=False)
    code |= evidence_code
    number_ids = collect_ids(numbers, ["numeric_id", "id"], "numbers", required=False)[1]
    number_by_id = {item_id(number, "numeric_id", "id"): number for number in numbers if item_id(number, "numeric_id", "id")}
    index_result_by_id = {item_id(result, "result_id", "id"): result for result in index_results if item_id(result, "result_id", "id")}
    claim_refs_by_id = {
        claim_id: set(strings(claim.get("evidence_ids")))
        for claim_id, claim in ((item_id(item, "claim_id", "id"), item) for item in claims)
        if claim_id
    }
    evidence_by_id = {
        evidence_id: item
        for evidence_id, item in ((item_id(item, "evidence_id", "id"), item) for item in evidence)
        if evidence_id
    }
    evidence_supports_by_id = {
        evidence_id: set(evidence_support_claim_ids(item))
        for evidence_id, item in evidence_by_id.items()
    }
    matrix_relationships = collect_evidence_matrix_relationships()
    reported_result_evidence_alignment: set[tuple[str, str, tuple[str, ...]]] = set()
    verified_result_ids = {
        result_id
        for result in status_results + index_results
        if is_verified(result) and (result_id := item_id(result, "result_id", "id"))
    }

    for result in status_results:
        result_id = item_id(result, "result_id", "id")
        if is_verified(result) and result_id not in index_ids:
            code |= error(f"verified result missing from result-index: {result_id}")
        index_result = index_result_by_id.get(result_id)
        code |= validate_result_ledger_parity(result, index_result)
        index_has_numeric_refs = result_numeric_refs(index_result)[1] if index_result else False
        if index_has_numeric_refs:
            continue
        refs, field_present, missing_entry_id = result_numeric_refs(result)
        if field_present and missing_entry_id:
            code |= error(f"result {result_id} numbers entries must include numeric_id/id")
        for numeric_id in refs:
            if numeric_id not in number_ids:
                code |= error(f"result {result_id} references unknown numeric id {numeric_id}")
        code |= validate_verified_result_active_claim_bindings(result, claim_ids, active_claim_id_set)
        code |= validate_result_claim_numeric_alignment(result, number_by_id)
        code |= validate_result_evidence_claim_alignment(
            result,
            claim_ids,
            evidence_by_id,
            claim_refs_by_id,
            evidence_supports_by_id,
            matrix_relationships,
            reported=reported_result_evidence_alignment,
        )
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
        refs, field_present, missing_entry_id = result_numeric_refs(result)
        if field_present and missing_entry_id:
            code |= error(f"result {result_id} numbers entries must include numeric_id/id")
        for numeric_id in refs:
            if numeric_id not in number_ids:
                code |= error(f"result {result_id} references unknown numeric id {numeric_id}")
        code |= validate_verified_result_active_claim_bindings(result, claim_ids, active_claim_id_set, verified=verified)
        code |= validate_result_claim_numeric_alignment(result, number_by_id)
        code |= validate_result_evidence_claim_alignment(
            result,
            claim_ids,
            evidence_by_id,
            claim_refs_by_id,
            evidence_supports_by_id,
            matrix_relationships,
            verified=verified,
            reported=reported_result_evidence_alignment,
        )
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
    claim_code, claim_ids = collect_ids(claims, ["claim_id", "id"], "claims", required=False)
    code |= claim_code
    active_claim_id_set = active_claim_ids(claims)
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
    code |= check_claim_numeric_literal_bindings(claims, number_by_id)

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
        code |= check_number_value_consistency(str(numeric_id), number)
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
            for claim_id in strings(number.get("claim_ids")):
                if claim_ids and claim_id not in claim_ids:
                    code |= error(f"number {numeric_id} references unknown claim {claim_id}")
                elif claim_ids and claim_id not in active_claim_id_set:
                    code |= error(f"verified number {numeric_id} references inactive claim {claim_id}")
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
    active_reference_keys = set()
    for ref in references:
        keys = reference_bibkeys(ref)
        for key in keys:
            reference_keys.add(key)
            if bib_keys and key not in bib_keys:
                code |= error(f"reference ledger bibkey missing from refs.bib: {key}")
        if active_now(ref):
            active_reference_keys.update(keys)
    for citation in citations:
        citation_id = item_id(citation, "citation_id", "id", "bibkey")
        for key in citation_bibkeys(citation):
            if key not in bib_keys and key not in reference_keys:
                code |= error(f"citation {citation_id} references unknown bibkey {key}")

    paper_keys = extract_cite_keys(read_paper_tex())
    citation_keys = set()
    active_citation_keys = set()
    for citation in citations:
        keys = citation_bibkeys(citation)
        citation_keys.update(keys)
        if active_now(citation):
            active_citation_keys.update(keys)
    if paper_keys and not reference_keys:
        code |= error("paper has citations but reference-ledger is empty")
    if paper_keys and not citation_keys:
        code |= error("paper has citations but citation-ledger is empty")
    for key in paper_keys:
        if key not in bib_keys:
            code |= error(f"paper cites missing BibTeX key: {key}")
        if key not in reference_keys:
            code |= error(f"paper cites key not registered in reference-ledger: {key}")
        elif key not in active_reference_keys:
            code |= error(f"paper cites key registered only in inactive reference-ledger entry: {key}")
        if key not in citation_keys:
            code |= error(f"paper cites key not registered in citation-ledger: {key}")
        elif key not in active_citation_keys:
            code |= error(f"paper cites key registered only in inactive citation-ledger entry: {key}")
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
    active_reference_keys = set()
    for ref in references:
        keys = reference_bibkeys(ref)
        reference_keys.update(keys)
        if active_now(ref):
            active_reference_keys.update(keys)
    citation_keys = set()
    active_citation_keys = set()
    for citation in citations:
        keys = citation_bibkeys(citation)
        citation_keys.update(keys)
        if active_now(citation):
            active_citation_keys.update(keys)

    if paper_keys and not citation_keys:
        code |= error("paper has citations but citation-ledger is empty")
    for key in paper_keys:
        if key not in bib_keys:
            code |= error(f"paper cites missing BibTeX key: {key}")
        if key not in reference_keys:
            code |= error(f"paper cites key not registered in reference-ledger: {key}")
        elif key not in active_reference_keys:
            code |= error(f"paper cites key registered only in inactive reference-ledger entry: {key}")
        if key not in citation_keys:
            code |= error(f"paper cites key not registered in citation-ledger: {key}")
        elif key not in active_citation_keys:
            code |= error(f"paper cites key registered only in inactive citation-ledger entry: {key}")

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
                elif key not in active_reference_keys:
                    code |= error(f"related-work area {area_id} cites key registered only in inactive reference-ledger entry: {key}")
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
    active_figure_ids = {
        ident
        for item in figures
        if isinstance(item, dict) and active_now(item)
        for ident in [item_id(item, "figure_id", "id")]
        if ident
    }
    active_table_ids = {
        ident
        for item in tables
        if isinstance(item, dict) and active_now(item)
        for ident in [item_id(item, "table_id", "id")]
        if ident
    }
    registry_code, claim_ids, numeric_ids, result_ids = load_float_registry_ids()
    code |= registry_code
    text = read_paper_tex()
    labels = extract_labels(text)
    refs = extract_refs(text)
    float_labels = {label for label in labels if float_label(label)}
    float_refs = {ref for ref in refs if float_label(ref)}
    mapped_labels = set()
    active_mapped_labels = set()
    for item in floats:
        float_id = item_id(item, "float_id", "id", "label")
        label = item.get("label")
        if not missingish(label):
            mapped_labels.add(str(label))
            if active_now(item):
                active_mapped_labels.add(str(label))
        if active_now(item):
            figure_id = item.get("figure_id")
            table_id = item.get("table_id")
            if not missingish(figure_id):
                if str(figure_id) not in figure_ids:
                    code |= error(f"active float {float_id} references unknown figure_id {figure_id}")
                elif str(figure_id) not in active_figure_ids:
                    code |= error(f"active float {float_id} references inactive figure_id {figure_id}")
            if not missingish(table_id):
                if str(table_id) not in table_ids:
                    code |= error(f"active float {float_id} references unknown table_id {table_id}")
                elif str(table_id) not in active_table_ids:
                    code |= error(f"active float {float_id} references inactive table_id {table_id}")
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
        elif label not in active_mapped_labels:
            code |= error(f"paper float label registered only in inactive float-placement entry: {label}")
    return code


def check_figures_tables():
    code = require(["lab/artifacts/figure-index.yaml", "lab/artifacts/table-index.yaml", "state/float-placement-map.yaml"])
    if code:
        return code
    code |= check_figure_table_wrapper_naming()
    figures = doc_items("lab/artifacts/figure-index.yaml", "figures")
    tables = doc_items("lab/artifacts/table-index.yaml", "tables")
    floats = doc_items("state/float-placement-map.yaml", "floats")
    code |= collect_ids(figures, ["figure_id", "id"], "figures", required=False)[0]
    code |= collect_ids(tables, ["table_id", "id"], "tables", required=False)[0]
    registry_code, claim_ids, numeric_ids, result_ids = load_float_registry_ids()
    code |= registry_code
    text = read_paper_tex()
    labels = extract_labels(text)
    refs = extract_refs(text)
    by_float_id, by_label, _, _ = float_maps(floats)
    active_by_float_id, active_by_label, _, _ = float_maps([item for item in floats if active_now(item)])
    paper_labels = labels | refs
    figure_labels = {label for label in paper_labels if figure_label(label)}
    table_labels = {label for label in paper_labels if table_label(label)}
    all_index_labels = {
        "figure": {
            label
            for item in figures
            for label in [label_for_index_item(item, by_float_id, by_label)]
            if label is not None
        },
        "table": {
            label
            for item in tables
            for label in [label_for_index_item(item, by_float_id, by_label)]
            if label is not None
        },
    }
    active_index_labels = {
        "figure": {
            label
            for item in figures
            if active_now(item)
            for label in [label_for_index_item(item, active_by_float_id, active_by_label)]
            if label is not None
        },
        "table": {
            label
            for item in tables
            if active_now(item)
            for label in [label_for_index_item(item, active_by_float_id, active_by_label)]
            if label is not None
        },
    }

    for kind, paper_kind_labels, path in [
        ("figure", figure_labels, "lab/artifacts/figure-index.yaml"),
        ("table", table_labels, "lab/artifacts/table-index.yaml"),
    ]:
        for label in sorted(paper_kind_labels):
            if label not in all_index_labels[kind]:
                code |= error(f"paper {kind} label is not registered in {path}: {label}")
            elif label not in active_index_labels[kind]:
                code |= error(f"paper {kind} label registered only in inactive {kind}-index entry: {label}")

    for kind, items in [("figure", figures), ("table", tables)]:
        for item in items:
            ident = item_id(item, f"{kind}_id", "id") or "<missing>"
            context = f"{kind} {ident}"
            label = item.get("label")
            float_id = item.get("float_id")
            mapped_float = mapped_float_for_index_item(item, by_float_id, by_label)
            active_mapped_float = mapped_float_for_index_item(item, active_by_float_id, active_by_label)
            mapped_label = label
            if missingish(mapped_label) and isinstance(mapped_float, dict):
                mapped_label = mapped_float.get("label")

            code |= check_path_field_values(item, context, ["path", "asset_path"])
            code |= check_provenance_paths(item, context)
            code |= check_registry_references(item, context, claim_ids, numeric_ids, result_ids)

            if active_now(item):
                if missingish(label) and missingish(float_id):
                    code |= error(f"active {kind} {ident} missing label or float_id")
                elif mapped_float is None:
                    code |= error(f"{kind} {ident} is not represented in state/float-placement-map.yaml")
                elif active_mapped_float is None:
                    code |= error(f"{kind} {ident} is represented only by inactive float-placement entry")
                if not missingish(mapped_label) and str(mapped_label) not in labels:
                    code |= error(f"{kind} {ident} label absent from paper tex: {mapped_label}")

                if not has_float_provenance(item):
                    code |= error(f"{kind} {ident} missing provenance")

                if kind == "figure" and not missingish(mapped_label):
                    code |= check_figure_asset_binding(
                        item,
                        mapped_float,
                        str(mapped_label),
                        ident,
                        text,
                        figures,
                        active_by_float_id,
                        active_by_label,
                    )

            if kind == "table" and table_requires_numeric_binding(item):
                has_numeric_binding = strings(item.get("numeric_ids")) or strings(item.get("result_ids"))
                if not has_numeric_binding and explicitly_qualitative(item):
                    table_label_value = mapped_label if not missingish(mapped_label) else label
                    numeric_literals = numeric_literals_in_latex(latex_block_for_label(text, str(table_label_value)))
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
    code |= check_unregistered_definitional_notation(symbols, paper_content)

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
            elif alias_key in seen_terms and alias_key != term:
                code |= error(f"duplicate term alias: {alias}")
            seen_terms[alias_key] = definition
    return code


def check_anonymity():
    code = require(["state/ccfa.yaml", "release/manifest.yaml"])
    if code:
        return code
    ccfa = load_doc("state/ccfa.yaml")
    team = ccfa.get("team", {}) if isinstance(ccfa.get("team"), dict) else {}
    if not anonymous_mode_enabled(team):
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
    venue_export_root = ROOT / "release/venue"
    if venue_export_root.exists():
        for path in venue_export_root.rglob("*-anonymous/**/*.tex"):
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


def anonymous_mode_enabled(team: dict) -> bool:
    mode = team.get("anonymous_mode", "")
    if mode is True:
        return True
    return str(mode).strip().lower() in {"anonymous", "double-blind", "blind", "anonymized"}


def declared_team_authors(team: dict) -> list[str]:
    authors = strings(team.get("authors"))
    if isinstance(team.get("authors"), str):
        authors = [part.strip() for part in team.get("authors", "").split(",") if part.strip()]
    skipped = {"", "todo", "anonymous", "anonymous author", "anonymous authors"}
    return [
        str(author).strip()
        for author in authors
        if normalize_metadata_text(author) and normalize_metadata_text(author) not in skipped
    ]


def check_project_metadata_consistency():
    code = require(["state/ccfa.yaml", "paper/main.tex"])
    if code:
        return code
    ccfa = load_doc("state/ccfa.yaml")
    paper = ccfa.get("paper", {}) if isinstance(ccfa.get("paper"), dict) else {}
    team = ccfa.get("team", {}) if isinstance(ccfa.get("team"), dict) else {}
    tex = read_paper_tex()

    declared_title = paper.get("title")
    if not missingish(declared_title):
        title_values = extract_tex_command_values(tex, "title")
        if not title_values:
            code |= error("state/ccfa.yaml paper.title has no paper \\title command to bind")
        else:
            declared = normalize_metadata_text(declared_title)
            actual_titles = [normalize_metadata_text(value) for value in title_values]
            if declared not in actual_titles:
                code |= error("state/ccfa.yaml paper.title does not match paper \\title")

    authors = declared_team_authors(team)
    if authors and not anonymous_mode_enabled(team):
        author_values = extract_tex_command_values(tex, "author")
        if not author_values:
            code |= error("state/ccfa.yaml team.authors has no paper \\author command to bind")
        else:
            author_text = normalize_metadata_text(" ".join(author_values))
            for author in authors:
                if normalize_metadata_text(author) not in author_text:
                    code |= error(f"state/ccfa.yaml team author missing from paper \\author: {author}")
    return code


def check_paper_populated(include_release: bool = True):
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
    code |= check_project_metadata_consistency()
    code |= check_claim_evidence()
    code |= check_numeric_consistency()
    code |= check_reference_existence()
    code |= check_citation_fitness()
    code |= check_figures_tables()
    code |= check_notation()
    code |= check_anonymity()
    if include_release:
        code |= check_release_package()
        code |= check_release_freshness()
    return code


def check_writing_harness():
    code = 0
    code |= require(["state/ccfa.yaml", "state/claim-evidence-map.yaml", "state/numeric-registry.yaml", "lab/research/reference-ledger.yaml", "paper/main.tex", "release/manifest.yaml"])
    code |= check_anatomy_drift()
    code |= check_capability_parity()
    code |= check_bridge_chassis_preflight()
    code |= check_paper_surface()
    code |= check_conference_template()
    code |= check_worktrees()
    code |= check_release_package()
    code |= check_release_freshness()
    code |= check_anonymity()
    populated = paper_looks_populated()
    if not populated:
        code |= check_project_metadata_consistency()
    if populated:
        code |= check_paper_populated(include_release=False)
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
    previous_revision = manifest.get("source_revision", {}) if isinstance(manifest.get("source_revision"), dict) else {}
    surfaces = normalized_surfaces
    manifest["manifest_version"] = RELEASE_MANIFEST_VERSION
    manifest["checksum_algorithm"] = CHECKSUM_ALGORITHM
    manifest["source_revision"] = source_revision()
    if meaningful(manifest["source_revision"]):
        code |= check_source_revision_matches_release_source(manifest)
        if code:
            return code
        previous_commit = previous_revision.get("commit")
        current_commit = manifest["source_revision"].get("commit")
        if previous_commit and current_commit and previous_commit != current_commit:
            print(f"INFO release manifest source_revision updated: {previous_commit[:12]} -> {current_commit[:12]}")
        elif not previous_commit and current_commit:
            print(f"INFO release manifest source_revision recorded: {current_commit[:12]}")
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
    flatten_record = flatten_release_surface(surfaces)
    manifest["flatten"] = [flatten_record] if flatten_record else []
    if flatten_record:
        status = flatten_record["status"]
        if status == "flattened":
            print(f"INFO release flatten {flatten_record['id']} produced at {flatten_record['path']}")
        elif status == "error":
            code |= error(f"release flatten {flatten_record['id']} latexpand failed: {flatten_record.get('error', '')}")
        else:
            print(f"INFO release flatten {flatten_record['id']} skipped: {status}")
    if code:
        return code
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return check_release_package() | check_release_freshness()


CHECKS = {
    "writing_harness": check_writing_harness,
    "paper_surface": check_paper_surface,
    "paper_populated": check_paper_populated,
    "anatomy_drift": check_anatomy_drift,
    "capability_parity": check_capability_parity,
    "bridge_chassis_preflight": check_bridge_chassis_preflight,
    "claim_experiment_plan": check_claim_experiment_plan,
    "conference_template": check_conference_template,
    "realkit_verification": check_realkit_verification,
    "lab_lightweight": check_lab_lightweight,
    "release_package": check_release_package,
    "release_freshness": check_release_freshness,
    "worktrees": check_worktrees,
    "human_gate_assets": check_human_gate_assets,
    "claim_evidence": check_claim_evidence,
    "result_status": check_result_status,
    "numeric_consistency": check_numeric_consistency,
    "numeric_exception_report": numeric_exception_report,
    "reference_existence": check_reference_existence,
    "citation_fitness": check_citation_fitness,
    "citation_review_worksheets": check_citation_review_worksheets,
    "citation_audit_report": citation_audit_report,
    "index_float_refs": lambda: require(["state/float-placement-map.yaml", "paper/figures/README.md", "paper/tables/README.md"]),
    "float_placement": check_float_placement,
    "notation": check_notation,
    "anonymity": check_anonymity,
    "figures_tables": check_figures_tables,
    "import_main_edits": lambda: require(["state/worktrees.yaml", "paper/ANATOMY.md"]),
    "export_release": export_release,
    "arxiv_portability": check_arxiv_portability,
}

REPORT_COMMANDS = {"numeric_exception_report", "citation_audit_report"}


def run(name: str) -> int:
    if name not in CHECKS:
        print(f"ERROR unknown check {name}")
        return 2
    code = CHECKS[name]()
    if code == 0 and name not in REPORT_COMMANDS:
        print(f"OK {name}")
    return code


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: paper_harness_checks.py <check-name>", file=sys.stderr)
        return 2
    return run(sys.argv[1])


if __name__ == "__main__":
    raise SystemExit(main())
