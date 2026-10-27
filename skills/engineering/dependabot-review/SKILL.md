---
name: dependabot-review
description: Review one dependency-bump pull request and file the ticket.
disable-model-invocation: true
argument-hint: "PR number or URL"
---

# Dependabot review

One GitHub pull request, reviewed from that repo's checkout. The run is done when the ticket comment is on the ref, or a command exits and names the reason.

Run `python3 <this-skill>/dependabot_review.py <command>` from the checkout. Each command prints one JSON object.

## 1. Packet

`dependabot_review.py packet <url-or-number> --out packet.json`

Done when it exits 0. Any other exit stops the run. Show `error`.

## 2. Verdict

Fetch `SKILL.md` from `thoughtbot/dependabot-review-skill-thoughtbot` at `main` with `gh api` and `Accept: application/vnd.github.raw`. Read **Step 2: Review Changelog & Breaking Changes** and **Step 4: Recommendation**. Map "Merge after verification" to `Verify`.

The changelog in the packet is the changelog. Write `verdict.json`:

```json
{
  "verdict": "Merge | Verify | Investigate | Hold",
  "one_line_reason": "one line",
  "breaks": [{ "kind": "symbol", "name": "identifier" }, { "kind": "behavior", "summary": "what changed" }],
  "impact": [{ "area": "area", "line": "what it touches" }],
  "security": false
}
```

A symbol names an identifier. A behavior break is a default, config, engine, or peer change. `security` is true when the changelog has a security fix.

`dependabot_review.py decide --packet packet.json --verdict verdict.json --out state.json`

Done when it exits 0. Show `review`. Exit 2: fix `verdict.json` and run `decide` again. Exit 3: the outcomes section is missing. Show `review` and stop.

`decide` sets the code-change bit. The summary stays the `deps |` line in `summary`.

## 3. Pull-request comment

`status_name` in the `decide` output is the status the next write will apply. Ask: post this review on PR #N? (yes / no / replace).

Yes: `comment --state state.json --confirm yes`. Replace: `--confirm replace`. No: skip the command. A result with `posted: false` and a `reason` is a skip. A result with `error` is reported, and the run continues.

Done when the comment is posted, skipped, declined, or the failure is reported.

## 4. Ref

`find-ticket --state state.json`.

GitHub returns `matches`. Jira returns `search.jql`: run that query and use the issues it returns. One match is the ref. Several matches: stop and name them. No match: call the Skill tool with `ticketer` and pass `ticket` from `state.json` (`summary`, `description`, `issue_type`, `priority`). If `priority` is rejected, drop it and draft again. Ticketer owns the other fields and its confirm.

Done when the ref exists. That ref is the input to the next step.

## 5. Status

When `status_name` is set, follow `references/<tracker>.md`. A missing reference stops before the ticket comment.

`status --state state.json --transitions <file> --fields <file>` emits the writes. Exit 4 stops before the ticket comment. Show `error`.

Done when the issue status is `status_name`, and a flag write matches `flag.value`.

## 6. Ticket comment

On a reused ref, save the prior comment that contains `dependabot-review:v1` and run `brief --state state.json --prior-file prior.md`. Otherwise run `brief --state state.json`.

When `post` is false, the run is done. When `post` is true, call the Skill tool with `terse` for the tracker's comment. The brief's first line stays first. Post that text on the ref. The tracker's reference says how.

Done when the comment is on the ref.
