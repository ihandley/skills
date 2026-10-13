# Build Stepper — Lightweight Working Memory for AI Coding Agents

You are building **Stepper**, a lightweight agent skill that prevents AI coding agents from losing track of outstanding work during long or complex conversations.

Before implementing anything, investigate the relevant agent skill and hook specifications, particularly for **Cursor and Claude Code**. Prefer established standards and native capabilities over custom infrastructure.

## Repository and Project Location

Stepper will be developed in the existing repository:

[https://github.com/ihandley/skills](https://github.com/ihandley/skills)

This repository is intended to contain reusable agent skills, not just Stepper.

Before proposing an architecture:

1. Inspect the repository's existing structure, conventions, documentation, and tooling.
2. Follow existing conventions where practical.
3. Implement Stepper as a self-contained skill within the repository, not as a standalone project.
4. Avoid introducing repository-wide dependencies or configuration unless absolutely necessary.
5. Keep runtime state separate from the skill's source files. Installing or updating the skill must not overwrite active tracking state.
6. Ensure the skill can be installed and used independently of other skills in the repository.
7. If the repository is empty or has no established conventions, follow the Agent Skills specification while retaining `skills/productivity/stepper/` as the skill's location.

Do not create a separate repository or initialize a new project.

Any installation instructions should reference this repository and explain how to install Stepper into Cursor and Claude Code.

Do not modify unrelated skills or repository files without a clear justification.

## The Problem

Coding agents frequently generate lists of outstanding work: unsatisfied acceptance criteria, unresolved bugs, implementation steps, review findings, etc.

These lists exist in conversation history. As work progresses, the agent and user can lose track of outstanding items, particularly when an individual item leads to a lengthy investigation.

For example:

1. An agent evaluates four acceptance criteria.
2. Two are satisfied; two are outstanding.
3. The user asks the agent to address the outstanding criteria.
4. The first outstanding criterion requires substantial investigation.
5. After completing it, the agent forgets the second criterion or concludes prematurely.

The user must then search conversation history or ask the agent to reconstruct the original list.

**Stepper solves this by preserving outstanding commitments and reminding the agent to return to them.**

Stepper is not a project planner, ticketing system, or TODO application. It is a lightweight working-memory mechanism.

## Architecture: Deterministic Core, Minimal Agent Involvement

Stepper must be designed as a deterministic state machine with a thin agent-facing skill and platform-specific hook adapters.

**The scripts are the source of truth. The agent is not.**

### Responsibilities of the deterministic core

Implement these operations in scripts without requiring LLM reasoning:

- Persist and load tracking state.
- Assign stable item identifiers.
- Track the current active item.
- Validate and enforce state transitions.
- Select the next actionable item.
- Maintain outstanding-item counts and progress.
- Prevent duplicate or invalid transitions.
- Generate compact reminders from current state.
- Detect whether tracked work remains incomplete.
- Restore state after session interruption.
- Handle explicit pause, resume, block, defer, and cancellation operations.
- Validate state integrity and handle corrupted or missing state safely.

Expose these operations through a small CLI with structured output suitable for hooks and agent consumption.

### Responsibilities of the agent

Use the agent only when semantic reasoning is necessary:

- Interpreting natural-language requests.
- Extracting actionable commitments from unstructured conversation.
- Understanding acceptance criteria.
- Performing implementation work.
- Evaluating whether completion criteria have been satisfied.
- Supplying evidence when requesting verification.

The agent must not manually edit the persistent state file. All state changes must go through the deterministic CLI.

### Hook architecture

Hooks must be thin adapters that invoke the deterministic core.

Do not duplicate state-management logic in platform-specific hooks.

Investigate supported Cursor and Claude Code hook events and select the smallest reliable set.

Use hooks for reminders, recovery, and lifecycle integration where supported.

Avoid per-tool-call LLM evaluation and repeated injection of unchanged state.

If hooks cannot guarantee a desired behavior, document the limitation rather than relying on unsupported assumptions.

### Testing requirements

The deterministic core must be independently testable without invoking Cursor, Claude Code, or an LLM.

Include tests for:

- State creation and persistence.
- Item activation and completion.
- Invalid state transitions.
- Evidence requirements.
- Blocked and deferred items.
- Resume after interruption.
- Multiple tracking contexts.
- Duplicate operations.
- Corrupted state recovery.
- Completion detection.
- Reminder generation.

Use actual platform integration tests separately.

### Performance and simplicity

Optimize for:

1. Correctness and reliability.
2. Minimal agent involvement.
3. Minimal token consumption.
4. Low operational overhead.
5. Small implementation footprint.

Do not sacrifice deterministic behavior merely to reduce the number of source files.

Prefer standard-library implementations and avoid external dependencies unless justified.

Do not introduce a database, daemon, web UI, or task-management framework.

Before implementation, provide a responsibility matrix identifying which behaviors are implemented deterministically, which require agent reasoning, and which depend on platform-specific hook capabilities.

Study Matt Pocock's skills repository for conventions around skill design and composability. Examine Planning with Files for its persistence and hook mechanisms, but **do not replicate its planning framework**.

## Core Capabilities



### 1. Capture

Users can explicitly activate Stepper:

- "Stepper, track these outstanding ACs."
- "Track those three issues."
- "Keep track of what's left."
- "Add this to Stepper."

The skill should extract actionable items from the relevant conversation context.

Preserve the original meaning and completion criteria. Do not invent requirements or silently discard items.

### Proactive capture (v1)

Stepper should also notice candidate actionable lists in agent output and offer to track them without explicit invocation. This is a core v1 requirement, not a future enhancement.

- Investigate which Cursor and Claude Code hook events can observe agent output and surface a suggestion. Do not assume either platform can directly prompt the user from a hook.
- Use deterministic parsing for recognizable patterns (Markdown checklists, numbered acceptance criteria, TODOs, unresolved findings) where possible.
- Distinguish candidate detection from deciding whether a list represents actual commitments. Use minimal agent judgment only when deterministic parsing is insufficient.
- Ask the user before activating tracking. Never silently enroll a list.
- Deduplicate suggestions for the same list, respect declined suggestions, and avoid nagging or interrupting ongoing work.
- If hooks cannot directly offer suggestions, use the closest documented mechanism to flag a candidate for the agent to offer at a natural conversational boundary; clearly document any reliability limits.
- Keep detection lightweight, avoid an LLM call on every message, and do not treat arbitrary numbered or illustrative lists as actionable by default.

### 2. Persistent State

Store the minimum information necessary to resume tracking across conversations, context compaction, and session restarts.

A single small Markdown, YAML, or JSON file is preferred.

Each tracked item needs:

- Stable identifier
- Description
- Status
- Optional completion evidence

The system also needs to identify the current active item.

Define one consistent, script-enforced state machine across the CLI, persistence format, hooks, and tests. Support at least:

- `pending` — outstanding and actionable.
- `active` — currently being addressed.
- `blocked` — cannot proceed until a stated dependency or condition changes.
- `verified` — completion established with appropriate evidence.
- `deferred` — explicitly postponed, not completed.
- `cancelled` — explicitly removed from scope, not completed.

Specify legal transitions, how blocked/deferred work is resumed, and whether terminal non-verified items count toward closure. Only verified items count as satisfied. Do not silently mark blocked, deferred, or cancelled items verified.

A verified item must have evidence appropriate to its completion criteria.

Avoid progress journals, research files, detailed plans, and automatically generated subtask trees.

Determine a sensible location and lifecycle for the state file. Consider repository hygiene, multiple workspaces, concurrent sessions, and whether the file should be committed.

Do not silently overwrite an existing active tracking session.

### 3. Maintain Focus

Stepper should know which commitment the agent is currently addressing.

If the agent investigates an unrelated problem while implementing an item, Stepper should preserve the original commitment without trying to track every intermediate action.

When the agent finishes the current item, it should return to the next outstanding item.

Do not automatically expand every discovered problem into a tracked subtask.

### 4. Reminders

Investigate Cursor's available hooks and Claude Code's hook mechanisms.

Implement the smallest reliable mechanism for reminding the agent of outstanding commitments at meaningful boundaries.

Potential triggers include:

- Before the agent concludes a tracked work session.
- After the agent completes an item.
- When the agent resumes after context compaction.
- When a new session resumes with active Stepper state.

Avoid injecting the full checklist on every tool call or message.

A reminder should be compact, for example:

`Stepper: AC-3 active; AC-4 pending. Do not conclude the tracked work until both are resolved or explicitly deferred.`

Distinguish between the agent ending an ordinary response and declaring the tracked work complete.

Do not prevent users from asking questions, pausing work, or changing direction.

**Important:** Do not assume hook events or capabilities exist. Verify them against current official documentation. If a desired behavior cannot be implemented reliably, document the limitation and implement the closest supported behavior rather than pretending it works.

### 5. Completion and Verification

When an item appears finished, the agent must verify its completion against the original requirement.

Examples:

- Tests pass.
- The required implementation is present.
- An expected behavior has been demonstrated.
- The user explicitly confirms a criterion that cannot be verified automatically.

Do not equate code changes with verified completion.

After verification:

1. Mark the item verified.
2. Identify the next outstanding item.
3. Return the agent's attention to that item.

When all items are verified, announce that the tracked work is complete.

Support explicit user-directed deferral, cancellation, or abandonment without falsely marking items verified.

### 6. Simple Interaction

Support natural-language operations such as:

- "What's left?"
- "Where are we?"
- "What's next?"
- "Mark that complete."
- "Add another item."
- "Pause Stepper."
- "Resume Stepper."
- "Stop tracking this."

Do not require users to memorize slash commands.

A dedicated `/stepper` command is acceptable as a convenience if the platform supports it.

## Implementation Constraints

Keep the implementation deliberately small.

Prefer:

- One `SKILL.md`.
- One persistent state file per tracking context.
- One or two small hook scripts, only if necessary.
- Minimal configuration.

Avoid:

- Databases.
- Web applications or dashboards.
- External services.
- Ticketing integrations.
- Complex task hierarchies.
- Background daemons.
- Large CLI frameworks.
- Unnecessary dependencies.
- Excessive token consumption.

If a native platform capability eliminates the need for custom code, use it.

The skill must not require a user to manually edit state files during normal operation.

## Required Investigation

Before coding:

1. Examine the current Agent Skills specification.
2. Examine Cursor's skill discovery and hook APIs.
3. Examine Claude Code's skill and hook APIs.
4. Review Matt Pocock's skills repository for relevant conventions.
5. Examine Planning with Files specifically for its hook-based persistence and recovery approach.
6. Identify existing implementations that could eliminate the need to write custom components.

Document only findings that materially affect the design.

Distinguish documented capabilities from assumptions.

## Testing

Create a realistic end-to-end test using this scenario:

An agent evaluates four acceptance criteria. AC-1 and AC-2 are already satisfied. AC-3 and AC-4 are outstanding.

The agent reports AC-3 and AC-4 as outstanding without the user invoking Stepper. Stepper detects the candidate list and offers to track it. The user accepts.

The agent begins AC-3 and encounters a complicated issue requiring multiple tool calls and an extended investigation.

Verify that:

1. Stepper proactively offers to track the two outstanding criteria, obtains user confirmation, and does not repeatedly offer the same list after a decline.
2. Stepper retains AC-3 and AC-4 throughout the investigation.
3. The agent does not prematurely declare the tracked work finished.
4. AC-3 is not marked verified without evidence.
5. After AC-3 is verified, the agent is reminded about AC-4.
6. After AC-4 is verified, Stepper announces completion.
7. State survives a fresh agent session.
8. Context compaction does not silently lose tracked commitments.
9. Pausing or asking unrelated questions does not trigger disruptive reminders.
10. A failed or unavailable hook does not corrupt state.

Use actual platform behavior for integration tests wherever possible. Do not represent mocked hook tests as proof of end-to-end platform integration.

## Deliverables

- Working Stepper skill.
- Required hooks and minimal supporting scripts.
- Persistent state format.
- Installation instructions for Cursor.
- Installation instructions for Claude Code, if supported.
- Brief README explaining usage and limitations.
- Tests demonstrating the core lifecycle.



## Development Process

First, investigate and propose the smallest viable architecture.

Explain:

- What will be implemented.
- Which hooks will be used and why.
- How state will persist.
- How Stepper will remain lightweight.
- Any platform limitations or reliability concerns.

**Present the proposed architecture and wait for my approval before writing implementation code.**

Do not broaden the scope into a general planning or task-management framework.

## Success Criterion

Stepper succeeds if an agent can capture two outstanding acceptance criteria, spend an extended period working on the first, and reliably return to the second without the user having to remind it.

Everything else is secondary.