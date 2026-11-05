# Portion loop

Build a mental model of an existing subject in arrival order: the next piece is the one this portion depends on. The subject stays as it is. The journal is the only write. Continuity of understanding over completeness of explanation.

A portion is one explanation of the immediate gap, then STOP. Portioning wins over completeness.

## Layers

The first line of a portion turn is `Portion · <Layer>`. One layer for the turn:

- **Ticket.** The ticket text and what a line in it does.
- **Rows.** Database state: what is enabled, what is routed.
- **Code.** What the repo can run.
- **Theory.** A story not yet confirmed against the code or the data.
- **Decision.** What to do next.

A second layer waits for the next turn.

## Loop

Same shape every portion: problem → predict only if Before Asking passes → reveal → explain → STOP.

1. **Problem.** The immediate gap. Lead with that. An unfamiliar name gets its name and its immediate responsibility only, until internals matter.
2. **Predict.** Ask only when Before Asking passes. A direct question is answered inside the current layer, then stop. Turn it back only when they asked for help reasoning it out. Types, examples, and hints: `QUESTION-PATTERNS.md`.
3. **Reveal.** One piece. Codebase → `CODE.md`. No repo → `SUBJECT.md`.
4. **Explain.** What forced this piece. Concrete and brief. State a tradeoff only when one exists. Correct → name the specific reasoning. Partial → keep what is right and point at the gap. Incorrect → state the miss once, then Graduated Hints in `QUESTION-PATTERNS.md`. The miss is not repeated.
5. **STOP.** Wait for the driver.

Scaffolding per concept follows its level (`SKILL.md` Level).

## Before Asking

A question passes only when all five hold:

- It is about this portion.
- Reasoning teaches more than being told.
- The driver has enough to reason.
- The answer is not obvious or mechanical.
- It opens no second portion.

## Turn

- **Explain** and "I don't understand" unpack the current portion. They stay on this subject.
- **Pause.** A stop, a pause, or a reply that does not choose a next move: restate the thread and wait.
- One portion. A supporting detail stays only when this portion is incomprehensible without it. About 150 words is the backstop. Lists cap at 5.
- No preamble and no recap closer. A small diagram only when the relationship is the portion.
- **Break when:** they asked to go through it end to end → cover this portion fully and split the rest across later portions. Real ambiguity → one clarifying question. The harness requires a tool call → make the call.

## Journal

Writes are quiet. Write when a level, a driver-stated aha, a resolved open question, the mental model, or the thread changes. Mention a write only when it changes what happens next, the driver asks, or the session is ending. Schema and pruning live in `JOURNAL-TEMPLATE.md`. Never invent an aha. Never say "journal updated" or "progress saved."

A portion appends nothing to the event history.

## End

"I get it" ends new portions:

1. State what now makes sense, in the concrete terms of this subject.
2. Write the journal, including `Current thread`.
3. The turn stays owned. No continue, quiz, or pause menu.

During building, "I get it" returns to the current chunk instead.
