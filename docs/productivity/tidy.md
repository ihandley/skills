## What it does

`tidy` lines up your local git branches with their pull requests and the issue tracker named in `~/.claude/tidy.yaml`, then deletes the branches whose commits the pull request already took.

The tracker comes from the active profile. Work uses Jira. Home closes GitHub issues. A branch that picked up commits after the pull request merged stays on disk. The ticket can still move. The branch delete waits for you.

## When to reach for it

Type `/tidy`, or the agent reaches for it when you say "tidy" or "clean up my branches", or you want merged branches deleted and their issues updated.

Reach for it after a batch of pull requests has merged and the local branches are still lying around. It is the wrong tool when you want a status report and nothing deleted.

## Common questions

**Will it delete a branch I kept working on after the pull request merged?**
No. If the local tip has commits the pull request never took, the branch stays. You get a separate choice about that delete.

**Does it know whether I am on Jira or GitHub issues?**
It reads `profile` in `~/.claude/tidy.yaml`. The example next to the skill shows both shapes. A missing file stops the run before anything changes.

**What about story points?**
On the Jira profile, every ticket still missing points is one list. The choices are 1, 2, and 3, with one recommendation and a sentence on why. The home profile does not ask.

## It's working if

- You saw one table before anything was deleted or transitioned.
- A branch with commits past the merged pull request is still there.
- Deleted branches come with a `git branch <name> <sha>` line you can paste to restore them.
- The Jira profile asked for story points once, for every ticket that needed them.
