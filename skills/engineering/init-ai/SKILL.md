---
name: init-ai
description: Generate or update a minimal AGENTS.md (plus a CLAUDE.md stub) for a project, following Anthropic's CLAUDE.md guidance. Use when the user asks to generate, create, or update AGENTS.md, or document a codebase for AI agents.
---

Write one accurate `AGENTS.md`, ≪100 lines root / 60 child (enforced at §4). No model file, no subdir sprawl by default, no invented architecture prose.

## §1 Preconditions

Existing root `AGENTS.md`:
- Absent → §2
- Present → surgical edit (add high-value facts, cut what fails §4). Ask first if intent differs substantially from this skill's output.

Ignore `.claude/repository-model.yaml` if present — do not render from it; mention once in §8.

## §2 Codesearch (optional)

Check whether a `codesearch` MCP server is already configured. None → skip straight to §3. Do not fail if missing, and do not invent an install path.

1. Check, host-appropriate:
   - Claude Code → `claude mcp list`
   - Cursor → `codesearch` entry in `.cursor/mcp.json` (project) or `~/.cursor/mcp.json` (global)
   - Other host → that host's MCP config/list mechanism
2. Present → ask once: "Use codesearch to verify organization-specific terms, services, and integrations while drafting? (y/n)". No → §3.
3. Yes → during §3–§4 use its lookup and cross-repo search to verify those terms before writing them. MCP-confirmed facts are verified (include if they pass §4; never `TODO(human)`).

## §3 Detect (scan, don't infer)

| Source | Keep |
|---|---|
| Manifests / build config (`package.json`, `go.mod`, `Cargo.toml`, `pyproject.toml`, `pom.xml`, `Makefile`, `kas/*.yaml`, …) | Copy-pasteable commands only; never invent one absent from a manifest/config |
| CI config | CI's actual command if ≠ local |
| Tree depth 1–2 | Pointer-worthy dirs only — not a full map |
| README / CONTRIBUTING / `.cursorrules` / human docs | Link, don't restate. Exception: core build/test/run commands stay even if README already has them |
| 2–3 source/test files | Confirm a *stated* convention is real — do not reverse-engineer new ones |

## §4 Draft

Every line must pass: **would removing this cause a mistake?** Else cut.

| Include | Exclude |
|---|---|
| Commands the model can't guess | Inferable from reading code |
| Style rules ≠ language defaults | Standard conventions models already know |
| Test runner / how to run tests | Detailed API docs (link) |
| Repo etiquette (branch/PR) | Frequently changing info |
| Architectural *decisions* (why X not Y) | Architecture *description* / import-graph restatements |
| Dev-env quirks (env vars, non-obvious setup) | Tutorials / long explanations |
| Gotchas w/ file refs | File-by-file codebase tour |
| Always / Ask first / Never — only if §3 found real destructive/prod surface | Blanket safety section with no destructive surface |
| | Self-evident practices; persona/role-play preambles |

Safety section (when applicable): name the actual §3 ops under **Always** / **Ask first** / **Never**.

Commands: exact invocation + checkable pass signal (exit 0, expected output, no unexpected diff).

No fixed section schema — headers that fit (`# Commands`, `# Conventions`, `# Gotchas`, …). Don't force Purpose/Architecture/Directory-Map.

Unverified (not mechanical, not codesearch, not human-stated) → do not guess:

```
<!-- TODO(human): add project-specific conventions/gotchas here -->
```

Mechanical gotchas (git history / CI patterns): include only if ≥2 occurrences or a known hazard of the detected tooling.

Root target ≪ 100 lines (script hard-fails at 100 root / 60 child).

**Audit before §6:** for each draft paragraph, name a plausible cost of omitting it (one phrase). Can't name one → cut or link. Show this audit with the draft at §6.

## §5 Subdirectories

No child `AGENTS.md` on file-count/config heuristics. Propose only if §3 found local, non-inferable knowledge that doesn't belong at root — ask before creating.

## §6 Confirm

Show detected facts + proposed write/edit (and §4 audit). Write only after user confirms.

## §7 Write

Write confirmed `AGENTS.md` path(s). Sibling `CLAUDE.md` must be exactly:

```
@AGENTS.md
```

| Existing `CLAUDE.md` | Action |
|---|---|
| Missing | Write stub |
| Already `@AGENTS.md` (whitespace ok) | Leave |
| Other real content | Don't touch; note path in §8 |

## §8 Verify + report

Run (don't hand-verify):

```
<this skill's dir>/scripts/check-agents-md.sh <repo-root>
```

`FAIL` → fix/cut before finish. `WARN` → carry into report (don't silently resolve).

Report: files written/edited; `TODO(human)` markers; untouched non-stub `CLAUDE.md` paths; every `WARN`; leftover `repository-model.yaml` if any.
