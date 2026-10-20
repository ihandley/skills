## What it does

`understand` builds a mental model of an existing subject in arrival order, one portion at a time, then stops. A portion is one or two instructions. A learning journal in the project keeps the thread so a later session can resume it.

A codebase is read in construction order: a short excerpt, then what forced that shape. Any other subject is one claim at a time, with a source you opened or an explicit note that the claim is the model's account.

It does not modify project source or config. The journal is the only file it writes.

## When to reach for it

Type `/understand`. The agent will not reach for it.

Use it to understand a codebase or any other subject one portion at a time. A direct question gets a direct answer, then the current thread resumes. For writing code while someone checks your reasoning, use `pair`.

## Common questions

**Does it edit the code I'm learning?**
No. Reads only. It writes `.claude/learning-journal.md` in that project and nothing else.

**Will it cover the whole subject in one turn?**
No. Each turn is one portion, then it waits.

**Will it quiz me after I asked something directly?**
No. A direct question gets a direct answer. It asks you to predict only when reasoning about this portion teaches more than being told.

**What if the subject has no files?**
Each claim names a source that was actually opened, or says it is the model's account.

## It's working if

- The turn states the immediate gap, reveals one piece, explains what forced it, and stops.
- A pause restates the thread and waits.
- A later session resumes from the journal's current thread.
- Project source and config are unchanged.
