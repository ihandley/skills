---
name: friction
description: Review one pasted workflow, separate friction from controls, and return a teardown, a blueprint, and a roadmap.
disable-model-invocation: true
---

# Friction

The workflow is the paste. The review is the only output of the turn.

**Workflow**: one repeating way the user gets a result, as they actually do it, including the tools and the hand steps.
**Friction**: motion or attention that neither changes the result nor stops a bad outcome.
**Control**: a step that exists to stop a bad outcome. Its cost is the motion or attention it takes. A measured cost appears only when the paste or a named file states it.
**Release**: the user's later message that a control they perform is no longer worth its cost. Until that message, the control stays in the blueprint.
**Quick**: a friction change that uses tools already present. Removing or reordering steps counts.
**Overhaul**: a friction change that replaces a tool, or adds a tool that is not present.
**Redirect**: another skill is the right reviewer.

## 1. One result

The paste names one result. Several results: name them and ask which. No workflow: ask for one. A request to review the session names agent-retro.

Done when one result is the subject.

## 2. Redirect

People produce this result by passing the work along. Stop. Name process-optimization: https://skills.sh/anthropics/knowledge-work-plugins/process-optimization

When it is not loaded:

`npx skills add https://github.com/anthropics/knowledge-work-plugins --skill process-optimization`

Done when the review has stopped, or the user performs the workflow.

## 3. Evidence

Open a path or command only when the paste names it. Anything else the review needs is an assumption, written as one.

Done when every named path or command was opened, or recorded as an assumption.

## 4. Classify

Every step is friction or a control. A control records its cost and what it protects. When the paste omits what a step protects and that decides the class, ask once. A step someone else performs is a control the user cannot release.

Done when every step has one class, and every control has a cost and a protection.

## 5. Write

- **Teardown.** Each friction, each control, each assumption.
- **Blueprint.** The workflow after every quick change and every overhaul. Every control remains.
- **Roadmap.** Friction changes only. Quick, then overhaul. Within each list, order by how many pasted steps the change removes. Each item names those steps. An item that names none is dropped.

Done when every step is in the teardown, every control is in the blueprint, and every friction change is in one roadmap list.
