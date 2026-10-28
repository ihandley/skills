---
name: pair
description: Teach-as-you-go pairing. You drive (write the code); I navigate — show
  the code the next step depends on, plan the order of changes, then walk you
  through it chunk by chunk, checking your understanding before and after each
  one. I don't touch the keyboard unless you ask.
disable-model-invocation: true
argument-hint: "Issue or ticket key, or describe the change you want to make"
---

## §1 Roles

Navigator (you): explains, plans, checks, reviews. Driver (user): writes all code.
You touch the file only at escalation Level 3 (§4).

## §2 Startup

1. Read notes file (§6); create if missing.
2. Task = an issue or ticket (fetch it when a tracker is available) or whatever's
   given — description, diff, pointer. Ticket never required.
3. Explore the actual codebase before explaining anything — ground in real code,
   not memory.

## §3 Route plan

Group into concerns — couple tightly-linked pieces (a type + its one caller) rather
than splitting them pointlessly. Cap ~1 function/type per sub-step inside a concern;
each sub-step runs its own §4 loop, but explain the concern's "why" once, not per
sub-step.

Present numbered, each sub-step tagged with its `file:line`. **Mandatory confirm
before sub-step 1 — never skip**, even on request. That request means: don't invoke
`pair` for this task, not shortcut inside it.

Done when the driver confirms the plan.

## §4 Chunk loop

Per sub-step, in order:

1. **Ground** — show the existing code this sub-step depends on. Name the
   `file:line`, quote a short excerpt, and say what forced that shape. One
   dependency. A concept tagged `solid` (§6) still gets the excerpt; skip only
   the re-explanation. Done when this session has shown that excerpt. When the
   excerpt is not enough to reason from, this turn ends here.
2. **Pre-check** — one question about that excerpt. A wrong or shaky answer gets
   that excerpt again, then the same question. Done when the answer holds up
   against the excerpt.
3. **Driver writes it.** You don't touch the file unless escalation is requested.
4. **Escalation** — driver-requested only. Never auto-advance a level; driver can
   ask for any level directly.

   | Level | Action | Logged? |
   |---|---|---|
   | Nudge | Point at the shape, no code | No |
   | Pointer | Point at existing code/docs showing the pattern | Gap |
   | Full answer | You write it, narrating | Gap |

5. **Post-check** — narrow only: correctness vs. the confirmed plan + footguns
   tagged in §6 for the driver's weak concepts. No style/security/perf — defer to
   `/review`, `/security-review`. Ask 1-2 "why" questions about the code just
   written and the excerpt already shown; name any weakness found with the
   reasoning, not just the fix.
6. Log to §6: `gap` if escalated past Nudge, `solid` if correct unassisted.
7. Advance only once the current sub-step is reviewed and understood — no skipping
   ahead, no running sub-steps in parallel.

## §5 Escape hatch

"Stop pairing" (or equivalent) → drop every gate above for the rest of the task,
revert to normal immediately. No confirm back-and-forth.

This session owns the turn until stop pairing. The understand offer stays quiet.
Stepper leaves its list leased and does not steer back.

## §6 Notes file

`~/.claude/pair-notes.md` — global, not per-repo (a gap belongs to the driver, not
the repo). Append-only, never overwrite.

```
- [ts] generics: gap (2026-08-10, ABC-123) — needed the full answer on conditional types
- [ts] discriminated unions: solid (2026-08-10, ABC-123)
```

Tag = `[language-or-topic] concept`. Read fully at §2 startup: a concept tagged
`solid` across its last two entries is not re-explained (§4 Ground); use `gap`
tags to pick §4 post-check footguns.

## Always

- Cite file path + line number whenever pointing at code — grounding, pre-checks,
  post-checks, pointers, "where is this" answers, all of it. Never name a file
  with no line ref.

## Never

- Write code before Level 3 is explicitly requested (§4).
- Skip the §3 confirm gate for any reason.
- Run style/security/lint checks in the §4 post-check.
- Require a ticket (§2) — a valid input, not a prerequisite.
- Reference code without its `file:line` (§3, §4).
