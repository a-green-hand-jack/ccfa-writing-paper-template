# Latex Checklist

- [ ] Inputs are registered.
- [ ] Required human gates are clear.
- [ ] Output paths are listed.
- [ ] Validator ran or validation gap is recorded.
- [ ] Fixes for LaTeX-safety or compile issues land in `paper/`, never in a `release/` export surface (see `.agent/latex-policy.md`).
- [ ] Before exporting an arXiv-bound release, the arXiv portability guardrail passed or its gap is recorded: standard TeX Live fonts only, no absolute paths, PDF/PNG/JPG figure assets preferred, no project macros defined inside a class file (`scripts/check-arxiv-portability.py`, `scripts/check-latex.sh --compile-release`).
