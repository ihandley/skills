## What it does

`understand` builds a mental model of an existing subject in arrival order, one portion at a time, then stops. A portion is one or two instructions. The first line of each turn names the layer: Ticket, Rows, Code, Theory, or Decision. A learning journal in the project keeps the thread so a later session can resume it.

While this session owns the turn, the subject stays the thread. Parked work stays parked until you say you have it or you ask to go back. The voice is a calm pair programmer: warm, matter-of-fact, a miss named once with where to look.

A codebase is read in construction order: a short excerpt, then what forced that shape. Any other subject is one claim at a time, with a source you opened or an explicit note that the claim is the model's account.

It does not modify project source, config, tickets, or drafts. The journal is the only file it writes.

## When to reach for it

Type `/understand`. The agent will not reach for it on its own.

With the hook installed, "I don't understand", "explain", and the same kind of phrase get one question: stay on this until it makes sense, or answer in place? Yes latches the session. `/understand` latches it without the question. An answer in place still labels each layer when a reply would mix them.

Use it to understand a codebase or any other subject one portion at a time. A direct question is answered inside the current layer, then the subject continues. For writing code while someone checks your reasoning, use `pair`. During `pair`, this offer stays quiet.

## Common questions

**Does it edit the code I'm learning?**
No. Reads only. It writes `.claude/learning-journal.md` in that project and nothing else.

**Will it cover the whole subject in one turn?**
No. Each turn is one portion and one layer, then it waits.

**Will it go back to the ticket I parked?**
The subject stays the thread until you say you have it or you ask to go back.

**How do I see that it is on?**
The first line is `Understand · Rows`, or whichever layer this turn is.

**Will it quiz me after I asked something directly?**
No. A direct question gets a direct answer inside the current layer. It asks you to predict only when reasoning about this portion teaches more than being told.

**What if the subject has no files?**
Each claim names a source that was actually opened, or says it is the model's account.

**Do I have to install the hook?**
No. `/understand` still owns the turn for the turns where the skill is loaded. The hook keeps the latch across later messages and asks before entering on an explanation phrase. From this skill's directory: `python3 turn.py hooks install claude` or `python3 turn.py hooks install cursor`. Claude injects the standing order on each prompt and after compaction. Cursor records the latch so stepper stays quiet. Cursor cannot inject that order on prompt submit.

## It's working if

- The first line is `Understand · <Layer>`, and the turn stays on that layer.
- The turn states the immediate gap, reveals one piece, explains what forced it, and stops.
- A pause restates the thread and waits.
- Parked work stays parked until you release the turn.
- A later session resumes from the journal's current thread.
- Project source, config, tickets, and drafts are unchanged.
