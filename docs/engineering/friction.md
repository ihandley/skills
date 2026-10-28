## What it does

`friction` reviews one workflow you paste: one repeating way you get one result, including the tools and the hand steps. It separates friction from controls and returns a teardown, a blueprint, and a roadmap.

The review is the only output of the turn. A control stays in the blueprint until you release a control you perform. A quick change uses tools already present, including removing or reordering steps. An overhaul replaces a tool, or adds one that is not present.

## When to reach for it

You type `/friction`. The agent will not reach for it.

Paste a workflow you perform. When other people produce the result by passing the work along, it names [process-optimization](https://skills.sh/anthropics/knowledge-work-plugins/process-optimization) and stops. When you ask it to review the session, it names agent-retro and stops.

## Common questions

**Will it change my keybindings or config?**
The review is the only output of the turn. A later message is what asks for a change.

**Will it tell me to drop a check that catches mistakes?**
A control stays in the blueprint until you release a control you perform. A step someone else performs stays a control you cannot release.

**What if I paste my whole morning?**
It names the results it sees and asks which one this review is.

**What if I did not measure how long a step takes?**
A measured cost appears only when the paste or a named file states it. Anything else is an assumption.

## It's working if

- One result is the subject.
- Every step is in the teardown as friction or a control, and every control names its cost and what it protects.
- The blueprint still contains every control.
- Every roadmap item names the pasted steps it removes, and no control is on the roadmap.
- Nothing on the machine changed.
