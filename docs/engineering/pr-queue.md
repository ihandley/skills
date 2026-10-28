## What it does

`pr-queue` lists the pull requests to review this week and tracks that list until you start `qpre`. It reads your team from `~/.claude/aliases.yaml`, takes the open sprint's `In Review` tickets first, then pull requests updated in the last 7 days.

The constraint is that the list is the whole job. The skill does not review the diff. A later "start" runs `qpre` on the active item, and the item stays active until you say the review is done.

## When to reach for it

Type `/pr-queue`. The agent will not reach for it.

Reach for it when you want the day's review queue. `/pr-queue backlog` is the open pull requests last updated more than 7 days ago. `all` on either command adds every other repo list on the team. For a review of one pull request you already have, use `pr-review`.

## Common questions

**Where do the people and repos come from?**
The `type: team` entry aliased "my team" in `~/.claude/aliases.yaml`. Authors are `members` and `qa`. The daily repos are `repos_active`. Sprint tickets are issues in an open sprint with status `In Review` whose Tech Domain is one of `jira_tech_domains`.

**What does a normal run show?**
One stepper list, not a table. In Review tickets stay in Jira rank, at any age. Recent pull requests are the ones updated in the last 7 days, newest first. A line such as `94 quiet` is the count of older open pull requests, including ones you already approved. Your own open pull requests stay in the recent section. A pull request you have approved on its latest commit does not.

**What is on a line?**
`repo#number`, the title, the author's name, and days since the last update. A mark appears only when it applies: a repo list other than `repos_active` (`eol`, `lib`, and the other names shortened the same way), `asked` when you are a requested reviewer, and `draft`, `merged`, or `closed`.

**What does start do?**
It runs `qpre` with the active item's pull request URL. A draft, merged, closed, or ticket-only item has no command to run. Saying the review is done strikes the item. Leaving `qpre` halfway leaves the item active.

**What does backlog show?**
A table of those older pull requests you have not approved on the latest commit, newest update first. A row number runs `qpre`.

**What does a second `/pr-queue` do?**
An unfinished sitting in this chat stays as it is, and nothing is fetched. An unfinished sitting nobody holds is attached to this chat. A finished sitting this chat holds, or that nobody holds, is closed and captured again from a fresh fetch. A sitting another chat holds stops the run and names that chat. A blocked or deferred item keeps the sitting.

**What if it stops before the queue?**
The Atlassian connection or the GitHub connection is missing, or the stepper hook never named this chat. The session line arrives with the first tool result. Install the stepper hook when that line is absent after those calls.

## It's working if

- The list matches the open sprint's `In Review` tickets in rank order, then pull requests updated in the last 7 days.
- A second `/pr-queue` leaves an unfinished sitting in place, and replaces a finished one.
- "Start" runs `qpre` with the full pull request URL, and the item stays until you say the review is done.
- The quiet count arrives without those older pull requests being downloaded.
