## What it does

`pr-queue` lists the pull requests to review this week and captures them as a sitting. It then walks them one at a time with `qpre` until you strike each item. It reads your team from `~/.claude/aliases.yaml`, takes the open sprint's `In Review` tickets first, then pull requests updated in the last 7 days.

The skill does not review the diff. `pr-queue` captures the list and stops. A later "start" runs `qpre` on the active item. When `qpre` exits the loop reads the outcome line, speaks it, and asks whether to strike the item.

## When to reach for it

Type `/pr-queue`. The agent will not reach for it.

Reach for it when you want the day's review queue. `/pr-queue backlog` is the open pull requests last updated more than 7 days ago. `all` on either command adds every other repo list on the team. For a review of one pull request you already have, use `pr-review`.

## Common questions

**Where do the people and repos come from?**
The `type: team` entry aliased "my team" in `~/.claude/aliases.yaml`. Authors are `members` and `qa`. The daily repos are `repos_active`. Sprint tickets are issues in an open sprint with status `In Review` whose Tech Domain is one of `jira_tech_domains`.

**What does a normal run show?**
One stepper list, not a table. In Review tickets stay in Jira rank, at any age. Recent pull requests are the ones updated in the last 7 days, newest first. The quiet count is every open pull request in the org last updated more than 7 days ago, including pull requests outside the daily repos and pull requests you already approved. Your own open pull requests stay in the recent section. A pull request you have approved on its latest commit does not. Drafts, merged, and closed pull requests are never rows. A bot's pull request is a row only when an In Review ticket links it.

**What is on a line?**
`repo#number`, the title, the author's name, and days since the last update. A mark appears only when it applies: a repo list other than `repos_active` (`eol`, `lib`, and the other names shortened the same way) or `asked` when you are a requested reviewer, and and nothing else.

**What if an In Review ticket has no pull request?**
It is a count beside the quiet count ("2 without a pull request"), not a row. The same goes for a ticket whose only pull requests are drafts, merged, closed, or already approved by you.

**Who captures the list?**
The script. It builds the lines, writes them into the stepper under the `pr-queue` context, and orders them free in one run. The agent only passes the Jira issues in and prints what comes back. A hand-written capture cost minutes in the first timed run, so the agent no longer writes one.

**What does start do?**
It runs `qpre` with the active item's pull request URL. Leaving `qpre` halfway leaves the item active.

**What happens when qpre exits?**
The loop reads the one outcome line `qpre` wrote and says `posted`, `clean`, or `unfinished`. It does not read the findings, which stay on the terminal. A missing line is a missing outcome, and you are still asked. You then strike the item or do something else. Something else returns to the same question. An unfinished walk still offers a strike.

**What does a strike do?**
It verifies the item with the outcome and your decision, then briefs the next item. `qpre` waits until you say start.

**What does backlog show?**
A table of those older pull requests you have not approved on the latest commit, newest update first. A row number runs `qpre` and captures nothing.

**What does a second `/pr-queue` do?**
An unfinished sitting in this chat stays as it is, and nothing is fetched. An unfinished sitting nobody holds is attached to this chat. A finished sitting this chat holds, or that nobody holds, is closed and captured again from a fresh fetch. A sitting another chat holds stops the run and names that chat. A blocked or deferred item keeps the sitting.

**What if it stops before the queue?**
The Atlassian connection or the GitHub connection is missing, or the stepper hook never named this chat. The session line arrives with the first tool result. Install the stepper hook when that line is absent after those calls.

## It's working if

- The list matches the open sprint's `In Review` tickets in rank order, then pull requests updated in the last 7 days.
- A second `/pr-queue` leaves an unfinished sitting in place, and replaces a finished one.
- "Start" runs `qpre` with the full pull request URL, and the item stays until you strike it.
- After `qpre` exits you hear `posted`, `clean`, or `unfinished`, and no findings.
- No draft, merged, closed, or approved pull request is in the list.
- The quiet count arrives without those older pull requests being downloaded.
- The list is printed from searches that return pull requests. A search that comes back empty stops the run and names the query.
- The run prints its total time from the prompt to the list, and it stays under five minutes.
