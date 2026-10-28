---
name: pr-queue
description: List this week's review queue, the open sprint's In Review tickets and the last 7 days of team pull requests.
disable-model-invocation: true
---

Build the queue by running the script beside this file, then stop. A `backlog` invocation does Stop and Script with `--backlog`. The backlog is not written into the ledger. Any other invocation does Stop, Sitting, and then either stops or does In review and Script. `all` adds `--all`. Later turns use what this invocation stored.

Run `date +%s` first and keep the number as the start time.

Call the Skill tool with `stepper` before any stepper command. The stepper CLI named in that skill is the one you run.

The script is `scripts/pr-queue` in the directory of this file. It reads `~/.claude/aliases.yaml`, fetches the pull requests, and prints the lines. Read that file only for `jira_project` and `jira_tech_domains`. Do not call `gh`. Do not rebuild the lines.

## Stop

Call `getAccessibleAtlassianResources` once and keep its cloud id and site URL. Call GitHub `get_me` once and keep its login. A missing MCP tool, a namespace that is not authenticated, or a failed call stops the run.

The viewer is the person aliased "me". That person's `ids.github` equals the login from `get_me`. Any other result: stop and print both logins. The script also checks this and exits when they differ.

On a list invocation, copy `--session` and `--root` from the hook line that starts with `Stepper session:`. Read it from the prompt, or from the context attached to those MCP results. A line that is still absent then stops the run: say the stepper hook did not provide a session key.

Done when the cloud id, the viewer, and (on a list invocation) a session key are in hand, or the run has stopped.

## Sitting

The context name is `pr-queue`. A capture outside this skill uses some other name.

On a list invocation, run `status` with no `--session` and find the context `pr-queue`.

- Another session holds it: stop and name that session. Do not fetch.
- This session holds it and `complete` is false: say the sitting is already there. Do not fetch.
- Nobody holds it and `complete` is false: `attach` it to this session. Do not fetch.
- This session holds it, or nobody holds it, and `complete` is true: `attach` first when nobody holds it, then `close` it, and continue to a fresh fetch.
- No `pr-queue` context: continue. Capture uses `--context pr-queue`.

`complete` is true only when every item is verified or cancelled and at least one item is verified. A blocked or deferred item leaves the sitting in place. A finished context with any other name stays leased until the user closes it. Attaching or rolling `pr-queue` leaves this session's other contexts leased.

Done when the run has stopped, an existing sitting is in this session, or a finished sitting was closed and a fresh fetch is next.

## In review

A list invocation searches Jira with `searchJiraIssuesUsingJql`. Page with `nextPageToken` until `isLast` is true. Fields are `summary`, `assignee`, and `updated`. Keep the result order. The record in `~/.claude/aliases.yaml` supplies `<jira_project>` and `<jira_tech_domains>` for this query only.

```
project = <jira_project> AND "Tech Domain[Dropdown]" in (<jira_tech_domains>) AND status = "In Review" AND sprint in openSprints() ORDER BY Rank ASC
```

Done when every issue from that JQL is held in rank order. A failed call stops the run.

## Script

Run `ruby` on `scripts/pr-queue` with `--viewer` set to the login from `get_me`. Pipe the Jira response to its stdin, unchanged. Pass `--started` with the start time. A backlog run passes `--backlog` and no issues. An `all` run passes `--all`.

Print its stdout. A non-zero exit stops the run. Say its stderr. A search that returns no pull requests is a non-zero exit that names the query. Print the `pr-queue total` line from stderr as the run time. It covers the clock from the prompt to the printed list, not only GitHub.

Done when stdout is printed.

## List

The printed lines are the list. An empty home is the quiet line and no capture.

Capture in home order under `--context pr-queue`. The id is the issue key, or `<key>-<repo>-<number>` when the issue has a pull request. A Recent id is `<repo>-<number>` after characters outside `A-Za-z0-9` are removed from the repo. An id that does not start with a letter gets a `pr-` prefix. Each `--item` is `id | text | criteria`. The text is the printed line.

Criteria for an open, non-draft pull request: `Start runs qpre on https://github.com/<github_org>/<repo>/pull/<number>. Done when the user says the review is done. Quitting qpre leaves the item active.`

Criteria otherwise: `No qpre: <draft, merged, closed, or ticket-only>. Done when the user says this item is done.` A ticket-only criterion includes the site URL from the Atlassian call plus `/browse/<key>`.

Then `order` with every id as `--item`, in the same order, and every id as `--free`.

Speak `done`, `left`, `blocked`, and `position` from `status`.

Done when the lines are printed, every item is free, and the four brief parts match `status`. qpre has not been started.

## Later

A later message uses the captured list or the printed table. It does not fetch again.

**Start** on a list runs `qpre` with the active item's pull request URL when that item's criteria say to start.

A **row number** on the backlog table runs `qpre` with that row's URL, rebuilt as `https://github.com/<github_org>/<repo>/pull/<number>`, when the pull request is open and not draft.

The user says the review is **done**: `verify` the active item with that evidence, then speak the four brief parts.

`skip` only when the user asks to skip. Quitting qpre leaves the active item active.

Done when qpre has been started for a startable item, or the item was verified, or a draft, merged, closed, or ticket-only item was named and qpre was not started.
