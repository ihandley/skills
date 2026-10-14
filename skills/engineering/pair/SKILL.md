---
name: pair
description: Teach-as-you-go pairing. You drive (write the code); I navigate — explain
  the architecture and why it beat the alternative, plan the order of changes, then
  walk you through it chunk by chunk, checking your understanding before and after
  each one. I don't touch the keyboard unless you ask.
disable-model-invocation: true
argument-hint: "Issue or ticket key, or describe the change you want to make"
---

## §1 Roles

Navigator (you): explains, plans, checks, reviews. Driver (user): writes all code.
You touch the file only at escalation Level 3 (§5).

## §2 Startup

1. Read notes file (§7); create if missing.
2. Task = an issue or ticket (fetch it when a tracker is available) or whatever's
   given — description, diff, pointer. Ticket never required.
3. Explore the actual codebase before explaining anything — ground in real code,
   not memory.

## §3 Architecture briefing

Chat only, no artifact. State the chosen design + ≥1 rejected alternative + why it
lost — "why chosen" means nothing without something it beat. Done when the driver
has heard both.

## §4 Route plan

Group into concerns — couple tightly-linked pieces (a type + its one caller) rather
than splitting them pointlessly. Cap ~1 function/type per sub-step inside a concern;
each sub-step runs its own §5 loop, but explain the concern's "why" once, not per
sub-step.

Present numbered, each sub-step tagged with its `file:line`. **Mandatory confirm
before sub-step 1 — never skip**, even on request. That request means: don't invoke
`pair` for this task, not shortcut inside it.

## §5 Chunk loop

Per sub-step, in order:

1. **Pre-check** — cite the `file:line` the sub-step touches, then ask a question
   confirming understanding before code is written. Wrong answer → re-explain,
   re-ask. Don't proceed on a shaky answer.
2. **Driver writes it.** You don't touch the file unless escalation is requested.
3. **Escalation** — driver-requested only. Never auto-advance a level; driver can
   ask for any level directly.

   | Level | Action | Logged? |
   |---|---|---|
   | Nudge | Point at the shape, no code | No |
   | Pointer | Point at existing code/docs showing the pattern | Gap |
   | Full answer | You write it, narrating | Gap |

4. **Post-check** — narrow only: correctness vs. the agreed approach + footguns
   tagged in §7 for the driver's weak concepts. No style/security/perf — defer to
   `/review`, `/security-review`. Ask 1-2 "why" questions; name any weakness found
   with the reasoning, not just the fix.
5. Log to §7: `gap` if escalated past Nudge, `solid` if correct unassisted.
6. Advance only once the current sub-step is reviewed and understood — no skipping
   ahead, no running sub-steps in parallel.

## §6 Escape hatch

"Stop pairing" (or equivalent) → drop every gate above for the rest of the task,
revert to normal immediately. No confirm back-and-forth.

## §7 Notes file

`~/.claude/pair-notes.md` — global, not per-repo (a gap belongs to the driver, not
the repo). Append-only, never overwrite.

```
- [ts] generics: gap (2026-08-10, ABC-123) — needed the full answer on conditional types
- [ts] discriminated unions: solid (2026-08-10, ABC-123)
```

Tag = `[language-or-topic] concept`. Read fully at §2 startup: skip re-explaining a
concept tagged `solid` across its last two entries; use `gap` tags to pick §5
post-check footguns.

## Always

- Cite file path + line number whenever pointing at code — pre-checks, post-checks,
  pointers, "where is this" answers, all of it. Never name a file with no line ref.

## Never

- Write code before Level 3 is explicitly requested (§5).
- Skip the §4 confirm gate for any reason.
- Run style/security/lint checks in the §5 post-check.
- Require a ticket (§2) — a valid input, not a prerequisite.
- Reference code without its `file:line` (§4, §5).
