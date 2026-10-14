---
name: agents-md
description: Write or update a minimal AGENTS.md. Use when the user asks to create or update AGENTS.md, or to document a codebase for agents.
---

# AGENTS.md

An `AGENTS.md` is a **cache**. The repo is the source of truth; the file holds only what an agent can't find by looking: the non-obvious command, the reason behind a decision, the gotcha no config confesses. Every line passes one test: **would an agent make a mistake without it?**

An existing `AGENTS.md` gets a surgical edit: check every command and path in it against the repo, fix what's stale, add what's missing, and cut what fails the test. If it's aiming at something different, ask before changing it.

## 1. Scan

Read the manifests, build config, CI, the top two levels of the tree, and the human docs (README, CONTRIBUTING). Open two or three source and test files only to confirm a convention the docs state. Every fact you write traces to one of these, or to the user.

## 2. Draft

What earns a line:

- Commands copied exactly from a manifest or CI, each with its pass signal (exit 0, expected output, clean diff). Use CI's command where it differs from local.
- Style rules that differ from the language's defaults.
- Decisions and their reasons: why X, not Y.
- Dev-environment quirks: env vars, non-obvious setup.
- Gotchas, each with a file reference. From git history or CI, only at two or more occurrences or a known hazard of the tooling.
- Branch and PR etiquette.
- **Always / Ask first / Never**, naming the destructive or production operations the scan found, when it found any.

Everything else stays in its source. Link human docs rather than restating them; core build, test, and run commands are the exception. Cache what stays true; fast-changing facts belong where they change.

Pick headers that fit the content (`# Commands`, `# Gotchas`). Where you can't verify a convention, write `<!-- TODO(human): ... -->` in its place.

Keep the root file well under 100 lines. A child `AGENTS.md` is for knowledge local to one subdirectory; propose it and ask before creating it.

## 3. Confirm

Show the user the draft, the facts behind it, and a one-phrase cost of omitting each paragraph. Cut any paragraph that has no cost. Write only after the user confirms.

## 4. Write

Write each `AGENTS.md`. Claude Code reads it directly, unless a `CLAUDE.md`, `.claude/CLAUDE.md`, or `CLAUDE.local.md` sits beside it or above it. Then Claude reads only that file, so ask to add this line at its top:

```
@AGENTS.md
```

Leave a `CLAUDE.md` that already imports it.

## 5. Check

Run this skill's `scripts/check-agents-md.sh <repo-root>` and fix every `FAIL`. Done when it passes and you've reported the files written, each `TODO(human)`, each `CLAUDE.md` left without the import, and every `WARN`.
