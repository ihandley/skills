## What it does

`dependabot-review` reviews one GitHub dependency-bump pull request and files the ticket for it. The code-change bit comes from a script. You write the verdict. Ticketer files the ticket, and terse writes the ticket comment.

The status and flag come from `~/.config/ticketer/outcomes.toml`, in the section named for the tracker. A missing section stops the run after the review is on screen.

## When to reach for it

You type `/dependabot-review`. The agent will not reach for it.

Use it on a Dependabot pull request, or any pull request whose diff is only a dependency bump, while your checkout is that repo. For any other pull request, use `pr-review`. `/pr-review` on a Dependabot author or a dependency bump tells you to run this command and stops.

## Common questions

**Where do the status names live?**
In `~/.config/ticketer/outcomes.toml`, under a section named `jira` or `github`. The skill does not contain those names.

**Will it post on the pull request?**
Only after you answer yes. A later run skips a pull request that already has this review, unless you say replace.

**What if the changelog cannot be fetched?**
The ticket is treated as a code change, and the comment says the changelog was not found.

## It's working if

- The review names the package, the bump, and whether a code change is required.
- The ticket summary is `deps | <pkg> <old>→<new> (PR #<n>)`.
- A code change lands in the configured status with the flag set. No code change lands in the other status, unflagged.
- The ticket comment starts with that code-change line, or with no code change.
