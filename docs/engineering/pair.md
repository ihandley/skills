## What it does

`pair` is a teach-as-you-go session. You write the code. The agent plans the change as small steps, shows the existing code each question depends on, and checks that you understand each step before and after you write it.

The agent does not edit files unless you ask for the full answer. A request to skip the plan confirmation means leave the skill, not skip the gate.

## When to reach for it

Type `/pair`. The agent will not reach for it.

Reach for it when you want to make a change yourself and have the agent navigate: the order of edits, the code each step depends on, and a check that you understand each chunk. It is the wrong tool when you want the agent to implement the change. When you want to learn the existing code and leave it unchanged, use `understand`.

## Common questions

**Do I need a ticket?**
No. A ticket, a description, a diff, or a pointer all work.

**Do I run understand first?**
No. Each question comes after the excerpt it uses.

**Will it write the code if I get stuck?**
Only when you ask. A nudge points at the shape. A pointer points at existing code. The full answer is the only level where it edits the file, and it logs that as a gap.

**Where do the notes go?**
`~/.claude/pair-notes.md`, one append-only log for you, not per repo. A concept marked solid on its last two entries is not re-explained. A gap becomes a footgun in the later check.

**Can I stop?**
Say "stop pairing". The gates drop for the rest of the task. Until then this session owns the turn: understand does not offer, and the stepper reminder stays quiet.

## It's working if

- You confirmed the numbered plan before the first step.
- Before each question, you saw the excerpt that question uses.
- You wrote each step. The agent edited a file only after you asked for the full answer.
- The notes file gained a `gap` or `solid` line for that step.
