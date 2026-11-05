# Building

The chunk loop. The driver writes every chunk. Three controls: the confirm, the question before they write, and the question after they write. The two questions differ by when they happen.

A building turn has no layer line. A one-portion detour from a chunk starts with its layer (`PORTION.md`).

## Route plan

Group the change into concerns. Couple tightly linked pieces (a type and its one caller) instead of splitting them. Inside a concern, about one function or type per chunk. Each chunk runs its own loop. Explain a concern's "why" once, not per chunk.

Present the plan numbered, each chunk tagged with its `file:line`.

**Confirm.** The driver confirms the plan before chunk 1. The confirm is a control. A request to skip it means this task is not a pairing session: the confirm stays, and `SKILL.md` Switch applies (name `stop pairing` once). The plan step ends when the driver confirms.

## Chunk loop

Per chunk, in plan order:

1. **Ground.** Show the existing code this chunk depends on: the `file:line`, a short excerpt, and what forced that shape. One dependency. No architecture tour and no pitch for the chosen design. Every level gets the excerpt.
   - Explore repo concept → one portion inside this grounding, then the turn stops.
   - The excerpt is not enough to reason from → the turn stops here.
2. **Question before they write.**
   - Familiar → no question.
   - Learning or Explore → one question about the excerpt, only when Before Asking (`PORTION.md`) passes.
3. **Driver writes it.** You do not touch the file.
4. **Escalation.** Driver-requested only. Never step up on your own. The driver can ask for any step directly.

   | Step | Action | Event history |
   |---|---|---|
   | Nudge | Point at the shape, no code | Nothing |
   | Pointer | Point at existing code that shows the pattern, with `file:line` | Gap |
   | Full answer | You write it, narrating. Only on the current chunk, only when asked | Gap |

5. **Question after they write.** Only when Before Asking passes. Narrow: correctness against the confirmed plan, and footguns from gap lines for the driver's weak concepts. Nothing on style, security, or performance. Name a weakness with the reasoning, not just the fix.
6. **Test run.** No prediction. Run it and read the result.
7. **A wrong answer** to either question → one portion on the miss, then the same question again.
8. **Record.** Fade the repo concepts this chunk exercised, in the journal. Append tooling lines to the event history (`SKILL.md` Tooling).
9. **Advance** only when the answer holds. No skipping ahead, no chunks in parallel.

A question about the current chunk → one portion, then back to this chunk at the same step.
