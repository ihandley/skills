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

**What does a row show?**
The pull request as `repo#number`, the title, the author, the age in days, and the approval count. A section heading carries a fact that is true of every row in it, such as `Still open · 18 · none approved`. A repo outside `repos_active` adds a short mark (`eol`, `lib`, and the other list names shortened the same way). `asked` appears when you are a requested reviewer. A sprint row also links its Jira key.

**What does a row number do?**
It runs `qpre` with that pull request's URL when the pull request is open and ready for review. A draft, merged, closed, or ticket-only row has no command to run.

**What if Jira or GitHub fails?**
The section from the source that returned still prints, with a line naming the source that failed.

## It's working if

- Sprint matches the open sprint's `In Review` tickets on the team board, in rank order.
- A pull request you have already approved is under Still open, unless a sprint ticket links it.
- A row number starts `qpre` with the full pull request URL, and the queue step ends before that.
