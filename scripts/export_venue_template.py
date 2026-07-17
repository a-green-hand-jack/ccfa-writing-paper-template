#!/usr/bin/env python3
"""Generate a venue-converted preview copy of paper/ paired with a
user-supplied official venue kit (CVPR/ICCV/NeurIPS/...), using
paper/style/compat.sty so paper/sections/*.tex compiles unmodified.

Never fetches a kit from the network: raw_template must already exist
locally (state/conference-template.yaml or --raw-template). Never edits
paper/, paper/refs.bib, or the official kit files it copies from.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_harness_checks import ROOT, load_doc, missingish  # noqa: E402

FORBIDDEN_SEGMENTS = {".git", ".github", ".agent", ".claude", ".agents", "state", "lab", "memory", "human"}
PAPER_COPY_ITEMS = ["sections", "figures", "tables", "generated", "refs.bib", "macros.tex"]
KNOWN_VENUE_OPTIONS = {
    "cvpr": {"anonymous": "review", "camera-ready": "final"},
    "iccv": {"anonymous": "review", "camera-ready": "final"},
    "neurips": {"anonymous": "preprint", "camera-ready": "final"},
}
REQUIRED_SECTION_ORDER = [
    "title",
    "abstract",
    "intro",
    "related",
    "method",
    "exp",
    "conclusion",
    "limitations",
]


def fail(message: str) -> int:
    print(f"ERROR {message}", file=sys.stderr)
    return 1


def resolve_raw_template(args) -> Path | None:
    if args.raw_template:
        return Path(args.raw_template).expanduser().resolve()
    template = load_doc("state/conference-template.yaml")
    raw = template.get("raw_template")
    if missingish(raw) or str(raw).strip().upper() == "TODO":
        return None
    text = str(raw).strip()
    if "://" in text:
        return None
    return (ROOT / text).expanduser().resolve()


def guard_no_forbidden_segments(paths) -> int:
    code = 0
    for path in paths:
        parts = set(path.parts)
        hit = parts & FORBIDDEN_SEGMENTS
        if hit:
            code |= fail(f"refusing to copy path with forbidden segment {hit}: {path}")
    return code


def copy_paper_sources(dest: Path) -> int:
    code = 0
    for item in PAPER_COPY_ITEMS:
        src = ROOT / "paper" / item
        if not src.exists():
            continue
        if src.is_symlink():
            code |= fail(f"paper/{item} is a symlink; refusing to export")
            continue
        out = dest / item
        if src.is_dir():
            files = [p for p in src.rglob("*") if p.is_file()]
            code |= guard_no_forbidden_segments(p.relative_to(src) for p in files)
            if code:
                continue
            shutil.copytree(src, out)
        else:
            shutil.copy2(src, out)
    compat = ROOT / "paper/style/compat.sty"
    if not compat.exists():
        return code | fail("paper/style/compat.sty is missing; run #8/#11 setup first")
    shutil.copy2(compat, dest / "compat.sty")
    return code


def copy_kit(raw_template: Path, dest: Path) -> tuple[int, list[Path], list[Path], list[Path]]:
    if not raw_template.exists():
        return fail(f"raw_template does not exist locally: {raw_template}"), [], [], []
    sources = [raw_template] if raw_template.is_file() else sorted(p for p in raw_template.rglob("*") if p.is_file())
    code = guard_no_forbidden_segments(p.relative_to(raw_template.parent) for p in sources)
    if code:
        return code, [], [], []
    # Kit files are copied flat into dest (not a subdirectory) so the
    # official class/style is found by kpathsea alongside the generated
    # main.tex, matching how conference submission zips are structured.
    cls_files, sty_files, bst_files = [], [], []
    for src in sources:
        if src.is_symlink():
            code |= fail(f"kit file is a symlink; refusing to copy: {src}")
            continue
        out = dest / src.name
        shutil.copy2(src, out)
        if out.suffix == ".cls":
            cls_files.append(out)
        elif out.suffix == ".sty":
            sty_files.append(out)
        elif out.suffix == ".bst":
            bst_files.append(out)
    return code, cls_files, sty_files, bst_files


def venue_option(venue_id: str, mode: str) -> str | None:
    return KNOWN_VENUE_OPTIONS.get(str(venue_id).strip().lower(), {}).get(mode)


def build_main_tex(*, cls_files, sty_files, bst_files, venue_id, mode, ccfa, anonymous) -> str:
    lines = []
    option = venue_option(venue_id, mode)
    opt_prefix = f"[{option}]" if option else ""
    if cls_files:
        lines.append(f"\\documentclass{opt_prefix}{{{cls_files[0].stem}}}")
        extra_sty = sty_files
    else:
        lines.append("\\documentclass{article}")
        extra_sty = sty_files
    for index, sty in enumerate(extra_sty):
        opts = opt_prefix if (index == 0 and not cls_files) else ""
        lines.append(f"\\usepackage{opts}{{{sty.stem}}}")
    if not sty_files and not cls_files:
        lines.append("% TODO: no .cls/.sty found in the official kit; add \\documentclass/\\usepackage by hand.")
    lines.append("\\usepackage{compat}")
    lines.append("\\input{macros}")

    paper = ccfa.get("paper", {}) if isinstance(ccfa.get("paper"), dict) else {}
    title = paper.get("title")
    lines.append(f"\\title{{{title if not missingish(title) else 'TODO Paper Title'}}}")
    if anonymous:
        lines.append("\\author{Anonymous Authors}")
    else:
        team = ccfa.get("team", {}) if isinstance(ccfa.get("team"), dict) else {}
        authors = team.get("authors")
        if isinstance(authors, list) and authors and not missingish(authors[0]):
            lines.append(f"\\author{{{', '.join(str(a) for a in authors)}}}")
        else:
            lines.append("\\author{TODO}")

    lines.append("\\begin{document}")
    for section in REQUIRED_SECTION_ORDER:
        lines.append(f"\\input{{sections/{section}}}")
    bibstyle = bst_files[0].stem if bst_files else "plain"
    lines.append(f"\\bibliographystyle{{{bibstyle}}}")
    lines.append("\\bibliography{refs}")
    lines.append("\\appendix")
    lines.append("\\input{sections/appendix}")
    lines.append("\\end{document}")
    return "\n".join(lines) + "\n"


def compile_check(dest: Path) -> int:
    if shutil.which("latexmk") is None:
        print("WARN latexmk not found; skipping compile verification")
        return 0
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [
                "latexmk", "-cd", "-pdf", "-interaction=nonstopmode",
                "-halt-on-error", "-file-line-error", f"-outdir={tmp}",
                str(dest / "main.tex"),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout[-4000:])
            print(result.stderr[-4000:])
            return fail(f"venue export failed to compile: {dest}")
    print(f"OK venue-compile {dest.relative_to(ROOT)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["anonymous", "camera-ready"], required=True)
    parser.add_argument("--raw-template", default=None, help="Local path to the official venue kit (overrides state/conference-template.yaml).")
    parser.add_argument("--no-compile", action="store_true", help="Skip independent compile verification.")
    args = parser.parse_args()

    raw_template = resolve_raw_template(args)
    if raw_template is None:
        return fail(
            "no local official venue kit configured; set state/conference-template.yaml "
            "raw_template to a local path or pass --raw-template (kits are user-supplied, never fetched)"
        )

    ccfa = load_doc("state/ccfa.yaml")
    venue = ccfa.get("venue", {}) if isinstance(ccfa.get("venue"), dict) else {}
    venue_id = str(venue.get("id") or "venue").strip().lower() or "venue"
    venue_year = str(venue.get("year") or "").strip()
    slug = "-".join(part for part in [venue_id, venue_year, args.mode] if part)

    dest = ROOT / "release" / "venue" / slug
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    code = copy_paper_sources(dest)
    if code:
        return code
    code, cls_files, sty_files, bst_files = copy_kit(raw_template, dest)
    if code:
        return code

    anonymous = args.mode == "anonymous"
    main_tex = build_main_tex(
        cls_files=cls_files, sty_files=sty_files, bst_files=bst_files,
        venue_id=venue_id, mode=args.mode, ccfa=ccfa, anonymous=anonymous,
    )
    (dest / "main.tex").write_text(main_tex, encoding="utf-8")
    (dest / "README.md").write_text(
        f"# {slug} venue export preview\n\n"
        "Generated by scripts/export-venue-template.sh from paper/ and a locally supplied "
        "official venue kit. Not a manifest-checksummed release surface; regenerate instead "
        "of hand-editing. paper/ and the official kit files are never modified by this process.\n",
        encoding="utf-8",
    )

    if not args.no_compile:
        code |= compile_check(dest)
    if code == 0:
        print(f"OK export_venue_template {dest.relative_to(ROOT)}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
