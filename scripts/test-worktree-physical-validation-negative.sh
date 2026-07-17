#!/usr/bin/env bash
# Negative-path regression for the worktree physical-validation gate (P20):
# proves scripts/check-worktrees.py hard-fails under the *shipped* defaults
# when an active worktree row names a branch that does not physically
# exist, and that the unmutated shipped state/worktrees.yaml still passes.
# Runs entirely against a disposable /tmp fixture (PAPER_HARNESS_ROOT
# override) -- never touches the live repo or its branches.
set -euo pipefail
cd "$(dirname "$0")/.."

FIXTURE="$(mktemp -d)"
LOG="$(mktemp)"
trap 'rm -rf "$FIXTURE" "$LOG"' EXIT

mkdir -p "$FIXTURE/state"
git init -q "$FIXTURE"
cp state/worktrees.yaml "$FIXTURE/state/worktrees.yaml"
git -C "$FIXTURE" -c user.name="fixture" -c user.email="fixture@example.invalid" add -A
git -C "$FIXTURE" -c user.name="fixture" -c user.email="fixture@example.invalid" commit -q -m "fixture"

if ! PAPER_HARNESS_ROOT="$FIXTURE" PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-worktrees.py >"$LOG" 2>&1; then
  echo "ERROR test-worktree-physical-validation-negative: clean shipped state/worktrees.yaml should pass check-worktrees.py but did not" >&2
  cat "$LOG" >&2
  exit 1
fi

python3 - "$FIXTURE/state/worktrees.yaml" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as handle:
    doc = json.load(handle)
for item in doc["worktrees"]:
    if item["id"] == "main":
        item["status"] = "active"
        item["branch"] = "this-branch-does-not-exist-anywhere"
with open(path, "w", encoding="utf-8") as handle:
    json.dump(doc, handle, indent=2)
PY

if PAPER_HARNESS_ROOT="$FIXTURE" PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-worktrees.py >"$LOG" 2>&1; then
  echo "ERROR test-worktree-physical-validation-negative: check-worktrees.py should hard-fail on an active worktree row with a nonexistent branch but exited 0" >&2
  cat "$LOG" >&2
  exit 1
fi

if ! grep -q "active worktree main branch does not exist: this-branch-does-not-exist-anywhere" "$LOG"; then
  echo "ERROR test-worktree-physical-validation-negative: expected a branch-does-not-exist error, got:" >&2
  cat "$LOG" >&2
  exit 1
fi

echo "OK test-worktree-physical-validation-negative: active-but-nonexistent branch caught under shipped defaults, clean tree still passes"
