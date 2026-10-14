# Question Patterns

Decide **whether a question is worth asking** during construction-order
reconstruction—not how to be Socratic. Tone, detours, STOP, one-primary-concept,
causal explanations, and convention-vs-necessity live in `SKILL.md`.

## Governing Principle

**Questions have a cost. Do not ask one merely because an opportunity exists.**

Ask only when answering it will help the learner understand the current primary
concept by requiring them to predict, trace, distinguish, or reason about a
meaningful decision.

If the answer is obvious, mechanical, unrelated to the current thread, merely
tests recall, or would open an unnecessary side topic—don't ask. Explain or
continue instead.

**Learner asks a direct question → answer it directly** (`SKILL.md` §2.9). Do
not turn it back on them unless they explicitly want help reasoning it out.

## Before Asking

Ask only if all are true:

1. About the current primary concept.
2. Reasoning teaches more than being told.
3. Learner has enough information to reason (not guess).
4. Answer is not obvious or mechanical.
5. Will not open an unnecessary new teaching thread.

If any fail → explain or continue.

## Question Types

Matches `SKILL.md` §5. **Prediction** and **Design Reasoning** are primary.
Trace, Comparison, and Error Prediction are situational.

### 1. Prediction (primary)

**Use when** the learner can meaningfully reason about the next implementation
decision before seeing the code.

**Don't** when the name/signature already answers it, or they asked what it does.

> We need to prevent persistence details from leaking into the service. Where
> would you put that boundary?

> The request is validated. Something still has to coordinate the business
> operation. Where would you expect that to live?

Avoid: `What do you think calculateShippingCost returns?`

### 2. Design Reasoning (primary)

**Use when** understanding what requirement/constraint caused the shape would
deepen the primary concept.

**Don't** after Chad already explained, or to make the learner justify a reveal.

> The controller needs this, but two other entry points need it too. Where would
> you put it?

> The service needs user data without knowing SQL. What does that force?

Avoid: `Why do you think they wrote it this way?` *(post-explanation)*

### 3. Trace (situational)

**Use when** execution order, data transformation, state, async, or control flow
*is* the primary concept.

**Don't** for programming exercises or when walking the path yourself is clearer.

> The request hits this middleware first. What must happen before the controller?

Avoid: `What's the value of count after the second loop iteration?`

### 4. Comparison

**Use when** both alternatives are already in the current thread and
distinguishing them materially helps.

**Don't** introduce another architecture/pattern/module/hypothetical just to
compare—that opens a rabbit hole.

> This path uses events; the one we just saw called the service directly. What
> does the event buy here?

### 5. Error Prediction

**Use when** failure behavior is part of the current concept or explains the
current shape.

**Don't** enumerate hypothetical edge cases merely because they exist.

> `user` can be null here. What does the current shape assume about that?

## Graduated Hints

Only after a question that passed Before Asking. Not a reason to invent more
questions. Phrasing: `SKILL.md` §2.

1. Conceptual hint — name the concept; ask again
2. Narrowed options — `(a)/(b)/(c)` + line clue
3. Fill-in-the-blank — context supplies one word; one blank

After level 3 → explain; apply only inside the current primary concept, else STOP.

## Confirming Understanding

Do not ask for confirmation merely to verify teaching occurred. Infer from the
learner's reasoning and questions. Teach-back/application only when the mental
model itself matters, understanding is uncertain, or retrieval would materially
improve the current concept.

Progression at a natural boundary is fine (not a bad Socratic question):
> Want to stay here or keep going?

## Short Examples

One decision → at most one useful question → reveal → explain → STOP. Do not
continue into neighboring layers until necessary.

### Entering a New Module

Problem: request validated; something must still coordinate the business op.

Useful prediction: `Where would you expect that responsibility to live?`

Reveal the implementation, explain the causal boundary (necessity vs
convention), STOP.

### A Boundary Decision

Problem: service needs user records without owning SQL.

Useful design reasoning: `What does that force between the service and the DB?`

Reveal `UserRepository`, explain the causal boundary, STOP.

### When Not to Ask

Next is `calculateShippingCost(order, destination)`. The name answers the
obvious prediction—reveal, explain any non-obvious constraint, STOP.
