#!/usr/bin/env bash
# Mechanical checks for agents-md AGENTS.md output. FAIL → exit 1; WARN → print only.
# Usage: check-agents-md.sh [repo-root]

set -euo pipefail

ROOT="${1:-.}"
cd "$ROOT"

FAIL=0
warn() { echo "WARN: $*"; }
fail() { echo "FAIL: $*"; FAIL=1; }

# Package-manager subcommands that aren't package.json scripts.
PM_BUILTINS="install i ci add remove rm uninstall update up upgrade rebuild exec dlx x create init
  link unlink publish pack prune outdated audit why list ls view info store config fetch dedupe"

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
  warn "${#AGENTS_FILES[@]} AGENTS.md files found. agents-md's rule: only add a child file for genuinely local, non-inferable content — confirm each one was a deliberate call, not default sprawl."
fi

for f in "${AGENTS_FILES[@]}"; do
  dir=$(dirname "$f")
  lines=$(grep -c "" "$f" || true)
  limit=100
  [ "$f" != "AGENTS.md" ] && limit=60
  if [ "$lines" -gt "$limit" ]; then
    fail "$f: $lines lines (limit $limit). Cut lines an agent could do without."
  fi

  if grep -qiE "you are an? .*(engineer|architect|developer|expert)" "$f"; then
    warn "$f: contains a persona/role-play preamble ('You are a(n) ... engineer/architect/...'). Common in the wild, unproven effect on modern models — consider cutting."
  fi

  for claude_md in "$dir/CLAUDE.md" "$dir/.claude/CLAUDE.md" "$dir/CLAUDE.local.md"; do
    if [ -f "$claude_md" ] && ! grep -qE '^[[:space:]]*@(\./)?AGENTS\.md[[:space:]]*$' "$claude_md"; then
      warn "$claude_md doesn't import @AGENTS.md. Claude Code reads it instead of $f, so add the import or confirm that was intentional."
    fi
  done

  while IFS= read -r span; do
    [ -z "$span" ] && continue
    if [[ "$span" == *[\*\?\[]* ]] || [[ "$span" == @* ]]; then
      continue
    elif [[ "$span" == */* ]] && [[ "$span" != *[[:space:]]* ]] && [[ "$span" != http* ]] && [[ "$span" != /* ]] && [[ "$span" != *...* ]]; then
      if [ ! -e "$span" ] && [ ! -e "$dir/$span" ]; then
        fail "$f: cites path '$span', which doesn't exist in the repo."
      fi
    elif [[ "$span" =~ ^[[:alnum:]_.-]+\.(md|json|jsonc|ya?ml|toml|lock|txt|ts|tsx|js|jsx|mjs|cjs|py|go|rs|sh)$ ]]; then
      if [ ! -e "$span" ] && [ ! -e "$dir/$span" ] && [ -z "$(find . -path ./node_modules -prune -o -name "$span" -print -quit)" ]; then
        fail "$f: cites file '$span', which doesn't exist in the repo."
      fi
    elif [[ "$span" =~ ^(npm|pnpm|yarn|bun)\ (run\ )?([^[:space:]]+) ]]; then
      script="${BASH_REMATCH[3]}"
      if [ -z "${BASH_REMATCH[2]}" ] && [[ " $PM_BUILTINS " == *" $script "* ]]; then
        continue
      fi
      if ! grep -rqF --include="package.json" -- "\"$script\":" . 2>/dev/null; then
        warn "$f: cites '$span', but no package.json defines a '$script' script."
      fi
    elif [[ "$span" =~ ^make\ ([^[:space:]]+) ]]; then
      if ! grep -rqE --include="Makefile" -- "^${BASH_REMATCH[1]}:" . 2>/dev/null; then
        warn "$f: cites '$span', but no Makefile defines a '${BASH_REMATCH[1]}' target."
      fi
    fi
  done < <(grep -oE '`[^`]+`' "$f" | sed -e 's/^`//' -e 's/`$//')
done

if [ "$FAIL" -eq 1 ]; then
  echo "--- FAILED: fix the above before shipping this AGENTS.md ---"
  exit 1
fi

echo "--- All hard checks passed (see warnings above, if any) ---"
