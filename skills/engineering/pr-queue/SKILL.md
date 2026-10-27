---
name: pr-queue
description: List the sprint tickets and team pull requests waiting for your review.
disable-model-invocation: true
---

Build the queue, print it, and end the turn. A later message that names a row runs qpre on that pull request.

## Record

Read `~/.claude/aliases.yaml`. The **record** is the `type: team` entry aliased "my team". The **viewer** is the person aliased "me".

Resolve authors (`members` and `qa` to `ids.github`), repos (every `repos_*` list, keeping the list name), `github_org`, `jira_project`, `jira_tech_domains`, and the viewer's `ids.github`.

Done when each of those is present, every author has `ids.github`, and the viewer login equals `gh api user`. Any other state: stop and name the missing key, or print both logins.

## Sources

A source that errors is a named line on the queue. Continue with the sources that returned.

### Sprint

JQL: `project = <jira_project> AND "Tech Domain[Dropdown]" in (<jira_tech_domains>) AND status = "In Review" AND sprint in openSprints() ORDER BY Rank ASC`. Page to the end.

**Link** each issue to pull requests by `JET-<digits>` in the head branch name, then in commit messages, then in the body. Search `github_org`. Keep each issue–pull-request pair. An issue with no key has no pull request.

Done when every issue from that JQL is held, each with its linked pull requests or with none.

### Qualify

A pull request **qualifies** when it is open, ready for review, its author is a User, and either the author is an author from the record or the repo is on a `repos_*` list.

Hold reviews and requested reviewers with each qualifying pull request and each linked pull request. Count Bot-authored open pull requests on those authors and repos. That count is the bot line.

Done when every qualifying pull request in `github_org` is held and the bot count is known.

## Home

Each pull request has one **home**, the first section it fits. Print sprint issues that have no pull request as their own Sprint rows.

1. **Sprint** — a sprint issue links it. Rank order.
2. **Needs you** — it qualifies, someone else opened it, and the viewer has no approval on the **head** (no APPROVED review whose commit is the head SHA). Oldest `createdAt` first.
3. **Still open** — it qualifies. Oldest `createdAt` first.

## Print

Columns: row number, PR, title, author, age, approvals. Row numbers run through the whole queue. Print a section when it has rows. The heading is `<Section> · <count>`, and when every row in that section has 0 approvals, add `· none approved`.

The PR cell is `[<repo>#<number>](<pull request url>)`. After the link, add a mark only when it applies:

- The repo's list, shortened: `eol`, `lib`, `infra`, `qa`, `tool`, `poc`, `disputed`, `verify`. `repos_active` has no mark.
- `asked`, when the viewer is a requested reviewer.
- `draft`, `merged`, or `closed`, when that is the pull request state.

A Sprint row also links the issue key to `https://liveviewtech.atlassian.net/browse/<key>`. A Sprint row with no pull request uses that issue link as the PR cell.

- Title is the pull request title, or the issue summary when the issue has no pull request.
- Author is the pull request author, or the issue assignee when the issue has no pull request.
- Age is whole days from the pull request `createdAt` to today, rendered `19d`. A row with no pull request uses the issue `created`.
- Approvals is the count of APPROVED reviews. Blank when the issue has no pull request.

Print the bot line after the sections. Print any source-failure line.

Done when each section that has rows, the bot line, and any source-failure line are printed, and qpre has not been started. End the turn.

## Row

A later message names a row number. Run `qpre` with that row's pull request URL when the pull request is open and ready for review.

Done when qpre has been started for that URL. A draft, merged, closed, or ticket-only row: say so and stop.
