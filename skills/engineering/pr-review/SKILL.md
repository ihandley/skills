---
name: pr-review
description: Review a GitHub pull request by fetching and following the LiveViewTech pr-review skill. Use when the user says "pr-review", "review this PR", "self-review", or pastes a pull request URL. Not Dependabot bumps.
argument-hint: "PR number or URL"
---

Fetch `plugins/lvt/skills/pr-review/SKILL.md` from `LiveViewTech/agent-config` via `gh api` with `Accept: application/vnd.github.raw` and `ref=main`. Follow that file.
