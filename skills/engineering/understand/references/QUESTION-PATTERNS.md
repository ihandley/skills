# Question Patterns

Types, examples, and hints for a question that already passed Before Asking in `SKILL.md`. Tone, detours, STOP, and the direct-answer rule live there.

## Question Types

**Prediction** and **Design Reasoning** are the usual types. Trace, Comparison, and Error Prediction are situational.

### 1. Prediction

**Use when** the learner can reason about the next piece before seeing it.

**Skip when** the name or signature already answers it, or they asked what it does.

> We need to prevent persistence details from leaking into the service. Where would you put that boundary?

> The request is validated. Something still has to coordinate the business operation. Where would you expect that to live?

> If every observer measures the same speed of light, what has to give for two events to be "at the same time"?

Skip: `What do you think calculateShippingCost returns?`

### 2. Design Reasoning

**Use when** the force that produced this shape would deepen the portion.

**Skip when** you already explained it, or the question only makes them justify a reveal.

> The controller needs this, and two other entry points need it too. Where would you put it?

> The service needs user data without knowing SQL. What does that force?

Skip: `Why do you think they wrote it this way?` after the explanation.

### 3. Trace

**Use when** execution order, data transformation, state, async, or control flow is the portion. For a subject with no repo, use it when the sequence of the claim is the portion.

**Skip when** walking the path yourself is clearer.

> The request hits this middleware first. What must happen before the controller?

Skip: `What's the value of count after the second loop iteration?`

### 4. Comparison

**Use when** both alternatives are already in the thread and distinguishing them changes the lesson.

**Skip when** the other alternative would be a new portion.

> This path uses events; the one we just saw called the service directly. What does the event buy here?

### 5. Error Prediction

**Use when** the failure behavior is part of this portion or explains the shape.

**Skip when** the edge cases are only a list of things that could go wrong.

> `user` can be null here. What does the current shape assume about that?

## Graduated Hints

Only after a question that passed Before Asking, and the answer was wrong. Phrasing follows `SKILL.md` Turn.

1. Conceptual hint. Name the concept and ask again.
2. Narrowed options `(a)/(b)/(c)` plus a line clue.
3. Fill-in-the-blank. The context supplies one word. One blank.

After level 3, explain. Ask them to apply it only if that application is still this portion. Otherwise STOP.

## Confirming Understanding

Infer understanding from their reasoning and their questions. Ask them to teach it back or apply it when the mental model itself is the portion, when understanding is uncertain, or when meeting the idea again would deepen this portion.

## Short Examples

One portion gets at most one question, then reveal, explain, STOP. Question text lives under Question Types.

### Entering a module

Problem: the request is validated, and something must still coordinate the business operation.

Prediction. Reveal the implementation, explain the boundary and whether it is necessity or convention, STOP.

### A boundary

Problem: the service needs user records and must not own SQL.

Design reasoning. Reveal `UserRepository`, explain the boundary, STOP.

### A claim the next one depends on

Problem: if every observer measures the same speed of light, simultaneity is in trouble.

Prediction. Reveal one claim, name the source, explain what forced it, STOP.

### When not to ask

The next function is `calculateShippingCost(order, destination)`. The name answers the obvious prediction. Reveal, explain any force that is not obvious, STOP.
