## What it does

`pr-queue` lists the pull requests and sprint tickets waiting for your review. It reads your team from `~/.claude/aliases.yaml` and prints three sections: Sprint, Needs you, and Still open.

The constraint is that the list is the whole job. A row number in a later message starts `qpre` on that pull request. The skill does not review the diff itself.

## When to reach for it

Type `/pr-queue`. The agent will not reach for it.

Reach for it when you want the review queue: the open sprint's `In Review` tickets, pull requests that still need your approval, and older open pull requests from the team or on a team repo. For a review of one pull request you already have, use `pr-review`.

## Common questions

**Where do the people and repos come from?**
The `type: team` entry aliased "my team" in `~/.claude/aliases.yaml`. Authors are `members` and `qa`. Repos are every `repos_*` list. Sprint tickets are JET issues in an open sprint with status `In Review` whose Tech Domain is one of `jira_tech_domains`.

**Does this clear my GitHub inbox?**
The queue is read-only. The inbox bookmarklet is still what marks notifications done.

**What does the key open?**
The pull request. The visible text is the issue key when the row has one, otherwise the pull request number. A row with no pull request opens the Jira issue.

**What does a row number do?**
It runs `qpre` with that pull request's URL. A row with an empty `qpre` cell has no command to run. Draft, merged, and closed pull requests stay visible when a sprint ticket links them, and the row shows that state.

**What if Jira or GitHub fails?**
The section from the source that returned still prints, with a line naming the source that failed.

## It's working if

- Sprint matches the open sprint's `In Review` tickets on the team board, in rank order.
- A pull request you have already approved is under Still open, unless a sprint ticket links it.
- A row number starts `qpre` with the full pull request URL, and the queue step ends before that.
