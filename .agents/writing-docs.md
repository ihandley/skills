# Writing docs pages

Every skill in `engineering/` and `productivity/` has a human-facing docs page at `docs/<bucket>/<skill-name>.md`. The page is not a copy of `SKILL.md`. Its job is to tell a person what the skill is for, when to reach for it, and how to tell it worked.

Create or re-sync the page when a promoted skill is added, renamed, or changes behaviour. A rename moves the file. A skill that moves between `engineering/` and `productivity/` moves its docs file with it. Skills in `misc/`, `in-progress/`, and `deprecated/` get no page. A promoted skill that is removed outright keeps its page: leave the body, and open it with a blockquote (`> **Archived.** ...`) naming the version it was removed in and any replacement.

Links inside a docs page are repo-relative.

There is no H1. The filename is the title.

## Page structure

Keep this order. A finished page has all four sections.

## What it does

One or two plain-language paragraphs. Lead with the skill's one-sentence job, then the single constraint that makes it behave differently from the obvious default.

## When to reach for it

- **Invocation mode.** A user-invoked skill: you type `/<name>`, and the agent will not reach for it. A model-invoked skill: type `/<name>`, or the agent reaches for it when a task fits.
- **Trigger boundary.** Reach for this when … Where it is easy to confuse with a sibling, name the sibling and when to use that one instead.

## Common questions

The questions a person actually asks before trusting the skill. Answer them in the skill's own vocabulary.

## It's working if

Observable outcomes. What the person should see when the skill did its job.
