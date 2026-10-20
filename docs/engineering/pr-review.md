## What it does

`pr-review` reviews a GitHub pull request by loading the LiveViewTech `pr-review` skill from `agent-config` and following it. The procedure is whatever is on `main` at review time, including sibling standards files that skill points at.

The constraint is that this repo stores the pointer. The review rules stay in `LiveViewTech/agent-config` and are read when the review runs.

## When to reach for it

Type `/pr-review`, or the agent reaches for it when you say "review this PR", "review PR 192", "self-review", or paste a pull request URL.

Reach for it on a pull request number, URL, or the pull request for the current branch. Dependabot bumps are outside this skill.

## Common questions

**Does this repo contain the review rules?**
It contains the fetch. The rules, NestJS standards, and GraphQL standards are read from `LiveViewTech/agent-config` when the review runs.

**What if GitHub access to that repo fails?**
There is no procedure to follow until that fetch succeeds.

**Will it post the review?**
Posting follows the fetched skill, including its confirmation gate before anything is submitted.

## It's working if

- The review uses the procedure fetched from `main`.
- The pull request number or URL you passed is the review target.
