#!/usr/bin/env bash
# Mechanical checks for init-ai AGENTS.md output. FAIL → exit 1; WARN → print only.
# Usage: check-agents-md.sh [repo-root]

set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

FAIL=0
warn() { echo "WARN: $*"; }
fail() { echo "FAIL: $*"; FAIL=1; }

AGENTS_FILES=()
while IFS= read -r line; do
  [ -n "$line" ] && AGENTS_FILES+=("$line")
done < <(find . -path ./.git -prune -o -path ./node_modules -prune -o \
  -path ./build -prune -o -name AGENTS.md -print | sed 's|^\./||')

if [ "${#AGENTS_FILES[@]}" -eq 0 ]; then
  echo "No AGENTS.md files found under $ROOT"
  exit 0
fi

if [ "${#AGENTS_FILES[@]}" -gt 2 ]; then
  warn "${#AGENTS_FILES[@]} AGENTS.md files found. init-ai's rule: only add a child file for genuinely local, non-inferable content — confirm each one was a deliberate call, not default sprawl."
fi

if [ -f .claude/repository-model.yaml ]; then
  warn ".claude/repository-model.yaml exists. init-ai ignores it; delete the file if nothing else needs it."
fi

for f in "${AGENTS_FILES[@]}"; do
  dir=$(dirname "$f")
  lines=$(grep -c "" "$f" || true)
  limit=100
  [ "$f" != "AGENTS.md" ] && limit=60
  if [ "$lines" -gt "$limit" ]; then
    fail "$f: $lines lines (limit $limit). Something on the exclude list crept back in — cut before adding more."
  fi

  if grep -qiE "you are an? .*(engineer|architect|developer|expert)" "$f"; then
    warn "$f: contains a persona/role-play preamble ('You are a(n) ... engineer/architect/...'). Common in the wild, unproven effect on modern models — consider cutting."
  fi

  claude_md="$dir/CLAUDE.md"
  if [ ! -f "$claude_md" ]; then
    fail "$claude_md missing — every AGENTS.md needs a sibling CLAUDE.md stub (@AGENTS.md), or Claude Code won't auto-load it."
  else
    content=$(tr -d '[:space:]' < "$claude_md")
    if [ "$content" != "@AGENTS.md" ]; then
      warn "$claude_md exists but isn't the plain '@AGENTS.md' stub — has other real content. Leave it, but confirm that was intentional."
    fi
  fi

  while IFS= read -r span; do
    [ -z "$span" ] && continue
    if [[ "$span" == */* ]] && [[ "$span" != http* ]] && [[ "$span" != /* ]] && [[ "$span" != *...* ]]; then
      if [ ! -e "$span" ] && [ ! -e "$dir/$span" ]; then
        fail "$f: cites path `$span` which doesn't exist in the repo."
      fi
    else
      if ! grep -rqF -- "$span" --include="package.json" --include="Makefile" \
        --include="*.yaml" --include="*.yml" --include="pyproject.toml" \
        --include="go.mod" --include="Cargo.toml" . 2>/dev/null; then
        warn "$f: cites `$span` — couldn't confirm this string appears in any manifest/config/CI file. Verify it's real before shipping."
      fi
    fi
  done < <(grep -oE '`[^`]+`' "$f" | sed -e 's/^`//' -e 's/`$//')
done

if [ "$FAIL" -eq 1 ]; then
  echo "--- FAILED: fix the above before shipping this AGENTS.md ---"
  exit 1
fi

echo "--- All hard checks passed (see warnings above, if any) ---"
