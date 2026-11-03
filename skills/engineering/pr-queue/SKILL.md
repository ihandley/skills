---
name: pr-queue
description: List this week's review queue, the open sprint's In Review tickets and the last 7 days of team pull requests, then walk them one at a time.
compatibility: Requires Ruby 2.6+ and the gh CLI
disable-model-invocation: true
---

Build the queue by running the scripts beside this file, then stop. A `backlog` invocation does Stop and Open's backlog line. Any other invocation does Stop, In review, and Open. `all` adds `--all`. Later turns use what this invocation stored.

Run `date +%s` first and keep the number as the start time.

Call the Skill tool with `stepper` before any stepper command. The stepper CLI named in that skill is the one you run.

The script is `scripts/pr-queue` in the directory of this file. It reads `~/.claude/aliases.yaml`, fetches the pull requests, and prints the lines. Do not read that file. Do not call `gh`. Do not rebuild the lines.

## Stop

Call GitHub `get_me` once and keep its login. A missing MCP tool, a namespace that is not authenticated, or a failed call stops the run.

The viewer is the person aliased "me". That person's `ids.github` equals the login from `get_me`. Any other result: stop and print both logins. The script also checks this and exits when they differ.

On a list invocation, copy `--session` and `--root` from the hook line that starts with `Stepper session:`. Read it from the prompt, or from the context attached to those MCP results. A line that is still absent then stops the run: say the stepper hook did not provide a session key.

Done when the viewer and (on a list invocation) a session key are in hand, or the run has stopped.

## In review

A list invocation runs the script with `--print-jql` and the `--viewer` login. It prints `cloud_id=`, `site=`, and `jql=` lines. A non-zero exit stops the run: say its stderr. Do not look the site up and do not build the query.

Search Jira once with `searchJiraIssuesUsingJql`, passing the printed cloud id and the text after `jql=`. Page with `nextPageToken` until `isLast` is true. Fields are `summary`, `assignee`, and `updated`. Keep the result order.

Done when every issue from that JQL is held in rank order. A failed call stops the run.

## Open

A list invocation runs `sitting open`, one command. `sitting` is `scripts/sitting` in the directory of this file. Write the issues to its stdin in the format below. Run `ruby` on it as `sitting open --session KEY --root PATH --stepper PATH --viewer LOGIN --started EPOCH`, with `--session` and `--root` from the hook line, `--stepper` the stepper CLI path named in the stepper skill, `--viewer` the login from `get_me`, and `--started` the start time. Add `--all` for an `all` invocation. Do not run stepper commands, apply lease rules, or call `pr-queue` yourself. `open` decides, fetches only when it must, and prints the queue and the four brief parts.

Print its stdout. A non-zero exit stops the run. Say its stderr, which names the chat when another chat holds the sitting.

Speak `done`, `left`, `blocked`, and `position` from the last four lines. Print the `pr-queue total` line from stderr as the run time when it is there. A run that fetched nothing has no total.

Issues go in one line each, in rank order: `KEY|assignee display name|updated|summary`. Use `unassigned` for no assignee. Do not write JSON. Do not read the scripts. Do not rebuild or retype their output.

A `backlog` invocation skips Open and runs `pr-queue` with `--viewer`, `--started`, and `--backlog`, sending no issues. Print its stdout and stderr totals.

Done when stdout is printed and the brief is spoken, or the run has stopped. Do not start qpre. An empty home is the quiet line and no capture.

## Later

A later message uses the captured list or the printed table. It does not fetch again.

**Start** on a list runs `qpre` with the active item's pull request URL and waits for it to exit. Quitting qpre leaves the item active.

After qpre exits, read the one outcome line qpre wrote for that pull request, and speak `posted`, `clean`, or `unfinished`. Read nothing else qpre wrote. The findings stay on the terminal. A missing outcome line is a missing outcome: say so, and prompt the same way.

Then ask the user to strike the item or do something else. Something else is handled, then the same question comes back. An unfinished walk still offers a strike.

A **strike** is the user's decision that the item is finished. Run `sitting strike --session KEY --root PATH --stepper PATH --evidence TEXT`, with the outcome and the user's decision as the evidence. Do not run `stepper verify` yourself. It verifies the active item and prints the next item's four brief parts, which you speak (`done`, `left`, `blocked`, `position`). Do not start qpre until the user says start. `sitting brief` with the same `--session`, `--root`, and `--stepper` prints the four parts again without changing anything.

A **row number** on the backlog table runs `qpre` with that row's URL, rebuilt as `https://github.com/<github_org>/<repo>/pull/<number>`. It captures no list.

`skip` only when the user asks to skip.

Done when qpre has been started for the active item, or a backlog row was named, or `sitting strike` ran and the next item was briefed.
