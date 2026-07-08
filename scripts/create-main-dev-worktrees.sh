#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR git is required to create worktrees" >&2
  exit 2
fi

WORKTREE_CONFIG="$(PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
import json
from pathlib import Path
try:
    import yaml  # type: ignore
except Exception:
    yaml = None
def load(path):
    text = Path(path).read_text(encoding="utf-8")
    return yaml.safe_load(text) if yaml else json.loads(text)
ccfa = load("state/ccfa.yaml")
worktrees = load("state/worktrees.yaml").get("worktrees", [])
by_id = {str(item.get("id")): item for item in worktrees if isinstance(item, dict)}
slug = ccfa["paper"]["slug"]
main = by_id.get("main", {})
dev = by_id.get("dev", {})
print(json.dumps({
    "slug": slug,
    "main_branch": main.get("branch") or f"{slug}-main",
    "main_path": main.get("path") or f"../{slug}-main",
    "sync_source": main.get("sync_source") or "release/overleaf",
    "dev_branch": dev.get("branch") or "dev",
}))
PY
)"
MAIN_BRANCH="$(python3 - <<'PY' "$WORKTREE_CONFIG"
import json, sys
print(json.loads(sys.argv[1])["main_branch"])
PY
)"
MAIN_PATH_DEFAULT="$(python3 - <<'PY' "$WORKTREE_CONFIG"
import json, sys
print(json.loads(sys.argv[1])["main_path"])
PY
)"
SYNC_SOURCE="$(python3 - <<'PY' "$WORKTREE_CONFIG"
import json, sys
print(json.loads(sys.argv[1])["sync_source"])
PY
)"
DEV_BRANCH="$(python3 - <<'PY' "$WORKTREE_CONFIG"
import json, sys
print(json.loads(sys.argv[1])["dev_branch"])
PY
)"
MAIN_PATH="${1:-$MAIN_PATH_DEFAULT}"

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
  if ! git rev-parse --verify "$DEV_BRANCH" >/dev/null 2>&1; then
    git branch "$DEV_BRANCH"
  fi
else
  git init -b "$DEV_BRANCH"
  git config user.name "${GIT_AUTHOR_NAME:-paper-harness}"
  git config user.email "${GIT_AUTHOR_EMAIL:-paper-harness@example.invalid}"
  git add -A
  git commit -m "Initialize evidence-first paper harness"
fi

if git rev-parse --verify "$MAIN_BRANCH" >/dev/null 2>&1; then
  MAIN_TREE_FILES="$(git ls-tree -r --name-only "$MAIN_BRANCH")"
  if grep -Eq '^(\.agent|\.claude|\.agents|state|lab|memory|human|exemplars)/' <<<"$MAIN_TREE_FILES"; then
    echo "ERROR target tex-only branch contains harness internals: $MAIN_BRANCH" >&2
    echo "Use a case-scoped branch in state/worktrees.yaml instead of rebuilding or deleting this branch." >&2
    exit 2
  fi
  git worktree add "$MAIN_PATH" "$MAIN_BRANCH"
  PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-worktrees.py
  echo "OK main worktree created at $MAIN_PATH from existing branch $MAIN_BRANCH"
  exit 0
fi

TMP="$(mktemp -d /tmp/paper-main-worktree.XXXXXX)"
cleanup() {
  if [ -d "$TMP/wt" ]; then
    git worktree remove --force "$TMP/wt" >/dev/null 2>&1 || true
  fi
  rm -rf "$TMP"
}
trap cleanup EXIT

mkdir -p "$TMP/surface"
if [ -d "$SYNC_SOURCE" ]; then
  cp -R "$SYNC_SOURCE/." "$TMP/surface/"
fi
if [ ! -f "$TMP/surface/main.tex" ]; then
  rm -rf "$TMP/surface"
  mkdir -p "$TMP/surface"
  if [ -f release/overleaf/README.md ]; then
    cp release/overleaf/README.md "$TMP/surface/README.md"
  else
    printf '# Tex-Only Main Surface\n\nGenerated from paper/.\n' > "$TMP/surface/README.md"
  fi
  for item in main.tex macros.tex venue_preamble.tex refs.bib sections figures tables style generated supplementary; do
    if [ -e "paper/$item" ]; then
      cp -R "paper/$item" "$TMP/surface/$item"
    fi
  done
fi

if find "$TMP/surface" -mindepth 1 -maxdepth 1 | grep -q .; then
  :
else
  echo "ERROR no tex-only surface files found in $SYNC_SOURCE or paper/" >&2
  exit 2
fi

if find "$TMP/surface" -mindepth 1 -maxdepth 1 | grep -Eq '/(\.agent|\.claude|\.agents|state|lab|memory|human|exemplars)$'; then
  echo "ERROR tex-only surface contains forbidden harness directories" >&2
  exit 2
fi

git worktree add --detach "$TMP/wt" HEAD
(
  cd "$TMP/wt"
  git switch --orphan "$MAIN_BRANCH"
  git rm -rf --ignore-unmatch . >/dev/null 2>&1 || true
  find . -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
  cp -R "$TMP/surface/." .
  git add -A
  if git diff --cached --quiet; then
    echo "ERROR no tex-only files staged for $MAIN_BRANCH" >&2
    exit 2
  fi
  git commit -m "Initialize tex-only main surface"
)
git worktree remove "$TMP/wt"

git worktree add "$MAIN_PATH" "$MAIN_BRANCH"
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-worktrees.py
echo "OK main worktree created at $MAIN_PATH from $MAIN_BRANCH"
