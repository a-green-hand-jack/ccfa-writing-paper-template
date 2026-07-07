#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR git is required to create worktrees" >&2
  exit 2
fi

SLUG="$(python3 - <<'PY'
import json
from pathlib import Path
try:
    import yaml  # type: ignore
except Exception:
    yaml = None
text = Path("state/ccfa.yaml").read_text(encoding="utf-8")
doc = yaml.safe_load(text) if yaml else json.loads(text)
print(doc["paper"]["slug"])
PY
)"
MAIN_PATH="${1:-../${SLUG}-main}"

if [ -e "$MAIN_PATH" ]; then
  echo "ERROR main worktree path already exists: $MAIN_PATH" >&2
  exit 2
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR commit or stash existing changes before creating worktrees" >&2
    exit 2
  fi
  git config user.name >/dev/null 2>&1 || git config user.name "${GIT_AUTHOR_NAME:-paper-harness}"
  git config user.email >/dev/null 2>&1 || git config user.email "${GIT_AUTHOR_EMAIL:-paper-harness@example.invalid}"
  if ! git rev-parse --verify dev >/dev/null 2>&1; then
    git branch dev
  fi
  git switch dev
else
  git init -b dev
  git config user.name "${GIT_AUTHOR_NAME:-paper-harness}"
  git config user.email "${GIT_AUTHOR_EMAIL:-paper-harness@example.invalid}"
  git add -A
  git commit -m "Initialize evidence-first paper harness"
fi

TMP="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP"
}
trap cleanup EXIT

if [ -f release/overleaf/README.md ]; then
  cp release/overleaf/README.md "$TMP/README.md"
else
  printf '# Tex-Only Main Surface\n\nGenerated from paper/.\n' > "$TMP/README.md"
fi
for item in main.tex macros.tex venue_preamble.tex refs.bib sections figures tables style generated supplementary; do
  if [ -e "paper/$item" ]; then
    cp -R "paper/$item" "$TMP/$item"
  fi
done

MAIN_NEEDS_REBUILD=0
if ! git rev-parse --verify main >/dev/null 2>&1; then
  MAIN_NEEDS_REBUILD=1
elif git ls-tree -r --name-only main | grep -Eq '^(\.agent|\.claude|\.agents|state|lab|memory|human|exemplars)/'; then
  MAIN_NEEDS_REBUILD=1
fi

if [ "$MAIN_NEEDS_REBUILD" -eq 1 ]; then
  if git rev-parse --verify main >/dev/null 2>&1; then
    git branch -D main
  fi
  git switch --orphan main
  git rm -rf . >/dev/null 2>&1 || true
  find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  cp -R "$TMP/." .
  git add -A
  git commit -m "Initialize tex-only main surface"
  git switch dev
fi

git worktree add "$MAIN_PATH" main
python3 scripts/check-worktrees.py
echo "OK main worktree created at $MAIN_PATH"
