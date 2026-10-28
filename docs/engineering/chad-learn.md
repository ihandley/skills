> **Archived.** Removed after version 0.2.0. Replaced by [understand](./understand.md).

## What it does

`chad-learn` reconstructs existing code in the order a developer could have built it, one decision at a time. It shows a short excerpt for the current decision, explains what forced that shape, and stops. A learning journal in the project keeps the thread so a later session can resume it.

It does not modify project source or config. The journal is the only file it writes.

## When to reach for it

Type `/chad-learn`. The agent will not reach for it.

Reach for it when onboarding to a codebase, or when you want to reconstruct how one piece of it works. For a direct question about a file, ask that question. This skill answers it, then returns to the current thread.

## Common questions

**Does it edit the code I'm learning?**
No. Reads only. It writes `.claude/learning-journal.md` in that project and nothing else.

**Will it walk the whole file in one turn?**
No. Each turn covers one decision, then waits.

**Will it quiz me after I asked something directly?**
No. A direct question gets a direct answer. It asks you to predict only when the next construction decision is the point of the turn.

## It's working if

- The turn states the immediate problem, shows a short excerpt, explains why that shape exists, and stops.
- A later session resumes from the journal's current thread.
- Project source and config are unchanged.
