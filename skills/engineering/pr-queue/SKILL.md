---
name: pr-queue
description: List this week's review queue, the open sprint's In Review tickets and the last 7 days of team pull requests, then walk them one at a time.
compatibility: Requires Ruby 2.6+ and the gh CLI
disable-model-invocation: true
---

Build the queue by running the script beside this file, then stop. A `backlog` invocation does Stop and Script with `--backlog`. Any other invocation does Stop, Sitting, and then either stops or does In review and Script, which also captures the list. `all` adds `--all`. Later turns use what this invocation stored.

Run `date +%s` first and keep the number as the start time.

Call the Skill tool with `stepper` before any stepper command. The stepper CLI named in that skill is the one you run.

The script is `scripts/pr-queue` in the directory of this file. It reads `~/.claude/aliases.yaml`, fetches the pull requests, and prints the lines. Read that file only for `jira_project` and `jira_tech_domains`. Do not call `gh`. Do not rebuild the lines.

## Stop

Call `getAccessibleAtlassianResources` once and keep its cloud id. Call GitHub `get_me` once and keep its login. A missing MCP tool, a namespace that is not authenticated, or a failed call stops the run.

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

Write the issues to the script's stdin as one line each, in rank order: `KEY|assignee display name|updated|summary`. Use `unassigned` for no assignee. Do not write JSON. Do not read the script. Do not rebuild or retype its output.

Run `ruby` on `scripts/pr-queue` with `--viewer` set to the login from `get_me` and `--started` set to the start time. Add `--all` for an `all` invocation. A backlog run adds `--backlog` and sends no issues.

A list run also passes `--session` and `--root` from the hook line, `--stepper` set to the stepper CLI path named in the stepper skill. The script prints the list, then captures every item under `--context pr-queue`, orders them all free, and prints a `pr-queue brief` line on stderr. Only open, non-draft pull requests you have not approved on the current head become items. An In Review ticket with no such pull request is counted beside the quiet count, not captured.

Print its stdout. A non-zero exit stops the run. Say its stderr. A search that returns no pull requests is a non-zero exit that names the query.

Speak `done`, `left`, `blocked`, and `position` from the `pr-queue brief` line. Print the `pr-queue total` line as the run time. It covers the clock from the prompt to the printed list, not only GitHub.

Done when stdout is printed, the brief is spoken, and the total is printed. The script has captured the list. Do not start qpre. An empty home is the quiet line and no capture.

## Later

A later message uses the captured list or the printed table. It does not fetch again.

**Start** on a list runs `qpre` with the active item's pull request URL and waits for it to exit. Quitting qpre leaves the item active.

After qpre exits, read the one outcome line qpre wrote for that pull request, and speak `posted`, `clean`, or `unfinished`. Read nothing else qpre wrote. The findings stay on the terminal. A missing outcome line is a missing outcome: say so, and prompt the same way.

Then ask the user to strike the item or do something else. Something else is handled, then the same question comes back. An unfinished walk still offers a strike.

A **strike** is the user's decision that the item is finished. `verify` the active item with the outcome and the user's decision as evidence, then speak the four brief parts for the next item. Do not start qpre until the user says start.

A **row number** on the backlog table runs `qpre` with that row's URL, rebuilt as `https://github.com/<github_org>/<repo>/pull/<number>`. It captures no list.

`skip` only when the user asks to skip.

Done when qpre has been started for the active item, or a backlog row was named, or the item was struck and the next item briefed.
