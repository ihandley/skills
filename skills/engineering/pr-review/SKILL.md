---
name: pr-review
description: Review a GitHub pull request by fetching and following the LiveViewTech pr-review skill. Use when the user says "pr-review", "review this PR", "self-review", or pastes a pull request URL. A Dependabot author or a dependency-bump pull request is /dependabot-review.
argument-hint: "PR number or URL"
---

A Dependabot author (`app/dependabot`) or a dependency-bump pull request is `/dependabot-review`. Tell the user to run it and stop.

Fetch `plugins/lvt/skills/pr-review/SKILL.md` from `LiveViewTech/agent-config` via `gh api` with `Accept: application/vnd.github.raw` and `ref=main`. Follow that file.
