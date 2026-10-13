# Stepper Architecture Proposal

Status: proposed, awaiting approval before implementation.

## Objective

Stepper is lightweight working memory for coding agents. It preserves a small set of outstanding commitments, keeps one item active, requires evidence before verification, and returns the agent to remaining work after a long investigation.

The scripts are the source of truth. The agent interprets language and performs work, but it does not edit state or decide state transitions itself.

## Research findings

Research was checked against the current official documentation on 2026-10-13:

- [Agent Skills specification](https://agentskills.io/specification)
- [Cursor Agent Skills](https://cursor.com/docs/skills)
- [Cursor hooks](https://cursor.com/docs/hooks)
- [Cursor third-party hooks](https://cursor.com/docs/reference/third-party-hooks)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Claude Code plugin components](https://code.claude.com/docs/en/plugins/components)
- [Matt Pocock's skills repository](https://github.com/mattpocock/skills)
- [Planning with Files](https://github.com/OthmanAdi/planning-with-files)

The hook findings below are documented capabilities, not inferred behavior. They still require live integration tests in each product before Stepper can claim end-to-end support.

### Cursor

Cursor loads command hooks from project or user `hooks.json` files. It does not load hooks merely because they are bundled inside an Agent Skill directory.

- `sessionStart` can add `additional_context` when a new composer conversation is created. It does not fire after compaction.
- `afterAgentResponse` receives completed assistant text but has no documented response fields. It can detect and record candidates, but cannot prompt the user or inject agent context.
- `stop` can return `followup_message`, which Cursor submits as another user message. Its input does not contain the assistant response text.
- `preCompact` is observational. It can show a user message but cannot alter compaction or add agent context.
- `postToolUse` can add `additional_context` after a tool result.
- `beforeSubmitPrompt` can inspect or block a prompt. It cannot rewrite the prompt or add model context.
- Stop follow-ups default to a limit of five per script and can be configured lower.
- User-level hooks do not run in Cursor cloud agents. Project hooks do.

Cursor can import Claude Code hooks from Claude settings when third-party imports are enabled. It maps the common lifecycle events and treats a Claude `Stop` block as a Cursor follow-up. Native Cursor configuration is still required for `afterAgentResponse`.

### Claude Code

Claude Code loads hooks from settings, a plugin's `hooks/hooks.json`, and invoked skill frontmatter.

- Plugin hooks register whenever the plugin is enabled.
- Skill-frontmatter hooks register only after that skill is invoked and remain for the rest of the session.
- `SessionStart` supports `startup`, `resume`, `clear`, `compact`, and `fork`. Its output can add context for Claude.
- `Stop` receives `last_assistant_message` and `stop_hook_active`. It can continue the conversation with non-error `additionalContext` or a blocking decision.
- `PreCompact` runs before compaction and can block it.
- `PostCompact` is available for side effects but cannot inject or control the next turn.
- `MessageDisplay` can alter display text only. It does not alter the transcript or what Claude sees.
- Command hooks cannot open an interactive terminal prompt.

Neither platform provides a hook that can directly ask the user whether a candidate list should be tracked. A hook can flag the candidate for the agent, which must ask at a natural turn boundary.

### Existing patterns

The Agent Skills specification supports a self-contained skill with a `SKILL.md`, scripts, references, and tests. This repository already adds `agents/openai.yaml`, promoted-skill documentation, README entries, and a Claude plugin manifest entry.

Matt Pocock's repository favors small, composable skills and explicit per-repository configuration. Stepper should follow those conventions without becoming a planning framework.

Planning with Files demonstrates the useful pattern of persistent disk state plus lifecycle reminders. Stepper will not copy its multiple planning files, progress journal, phase tracking, transcript recovery, or per-tool recitation. It will keep one minimal state machine and inject compact reminders only at meaningful boundaries.

Native Claude tasks and Cursor todos do not replace the deterministic core. They are platform-specific and model-managed, and they do not provide a shared evidence-checked state machine.

## Proposed structure

```text
skills/productivity/stepper/
├── SKILL.md
├── README.md
├── agents/
│   └── openai.yaml
├── stepper.py
└── tests/
    └── test_stepper.py
```

`stepper.py` will contain the standard-library CLI and hook adapter entry point. Hook commands will call that CLI rather than contain state logic.

Stepper will be a model-invoked productivity skill. Users can invoke it explicitly, and an agent can reach for it when a request asks to retain outstanding commitments.

## Persistent state

Runtime state will live under the consuming repository's `.stepper/` directory, separate from the installed skill:

```text
.stepper/
├── current
├── contexts/
│   └── <context-id>.json
├── runtime.json
└── suggestions.json
```

- One JSON file represents one tracking context.
- `current` identifies the context used by hooks and default CLI commands.
- `runtime.json` stores hook bookkeeping such as the last processed generation and compaction markers.
- `suggestions.json` stores candidate hashes and whether they were offered, accepted, or declined.
- Installation will add `.stepper/` to `.git/info/exclude`, not the repository's committed `.gitignore`.
- Creation will fail rather than overwrite an active context unless replacement is explicit.
- Writes will use a lock, temporary file, and atomic rename.
- A corrupt file will be moved aside with a timestamp. Interactive CLI commands will report the error; hook commands will fail open without changing state.

Each item will contain:

- Stable identifier
- Description
- Completion criteria
- Status
- Optional evidence
- Optional blocked reason
- Stable order

Source identifiers such as `AC-3` will be preserved. Otherwise the CLI will assign monotonic identifiers and never reuse them.

## State machine

Supported statuses:

- `pending`: outstanding and actionable
- `active`: the single item currently being addressed
- `blocked`: waiting for a stated dependency or condition
- `verified`: completion established with evidence
- `deferred`: explicitly postponed
- `cancelled`: explicitly removed from scope

Legal transitions:

| From | To |
| --- | --- |
| `pending` | `active`, `deferred`, `cancelled` |
| `active` | `pending`, `blocked`, `verified`, `deferred`, `cancelled` |
| `blocked` | `pending`, `active`, `deferred`, `cancelled` |
| `deferred` | `pending`, `cancelled` |
| `verified` | none |
| `cancelled` | none |

Only one item may be active. Verification requires non-empty evidence. The CLI validates that evidence exists; the agent determines whether the evidence satisfies the original completion criteria.

Verifying the active item activates the next pending item in stable order. Blocked and deferred items are skipped when selecting the next actionable item.

A context is complete when every item is either verified or cancelled and at least one item is verified. Cancelled work is out of scope, not satisfied. Deferred work remains incomplete. Blocked work remains outstanding.

Pausing affects the context, not item statuses. Hooks remain quiet until the context is resumed. Stopping tracking closes the context without changing unfinished items to verified.

## CLI

The CLI will expose structured JSON by default for hooks and agent consumption, plus compact human-readable output where useful. The operation set will stay small:

- `start`
- `capture`
- `add`
- `status`
- `next`
- `activate`
- `verify`
- `block`
- `unblock`
- `defer`
- `resume-item`
- `cancel`
- `pause`
- `resume`
- `stop`
- `detect`
- `suggest`
- `install-hooks`
- `hook`

All mutations go through these operations. `SKILL.md` will explicitly forbid manual state-file editing.

Duplicate operations will be idempotent where the requested end state already holds and rejected where repeating them would lose information.

## Proactive capture

Candidate detection will be deterministic and conservative.

The parser will accept lists only when nearby text identifies outstanding work, such as remaining acceptance criteria, unresolved findings, failures, or TODOs. It will recognize Markdown checklists, numbered criteria, and explicit status words. It will ignore checked or satisfied items, illustrative lists, and unqualified numbered lists.

The normalized candidate list will be hashed. Suggestion state will move through:

```text
unseen -> offered -> accepted
                 \-> declined
```

A declined hash will not be offered again. A candidate found while another context is active will be recorded but not interrupt that work.

Hooks never activate tracking. At a natural stop boundary they can tell the agent that a candidate exists. The agent asks the user once and calls `capture` only after acceptance. Lists outside the deterministic parser remain available through explicit user capture; Stepper will not add an LLM call to every message.

## Hook architecture

Hooks will be installed explicitly because installing an Agent Skill does not register all required hooks on either platform.

All hooks will:

- Call the same `stepper.py` core.
- Exit quickly and silently when no context or candidate is relevant.
- Fail open on script errors.
- Avoid LLM-evaluated hook types.
- Deduplicate by platform generation or prompt identifier.
- Never modify item state implicitly.

### Claude Code adapter

User-level Claude settings will register:

1. `SessionStart` for `startup`, `resume`, and `compact`: inject one compact reminder when outstanding work exists.
2. `UserPromptSubmit`: record enough prompt context to distinguish tracked work from unrelated questions without injecting a reminder.
3. `Stop`: inspect `last_assistant_message`, detect candidates, and continue once when tracked work would otherwise be forgotten.
4. `PreCompact`: record a compaction marker without blocking compaction.

The Stop adapter will exit without continuation when Stepper is paused, when `stop_hook_active` indicates a prior continuation, or when the turn was an unrelated question.

### Cursor adapter

User-level Cursor settings will register:

1. `sessionStart`: inject one reminder for a new composer.
2. `beforeSubmitPrompt`: record prompt context only.
3. `afterAgentResponse`: inspect completed assistant text and run candidate detection.
4. `stop`: use stored response data and emit at most one follow-up (`loop_limit: 1`).
5. `preCompact`: record a marker.
6. `postToolUse`: inject one reminder after compaction when the marker is present, then clear it.

If imported Claude settings and native Cursor hooks both fire, the CLI's generation-level deduplication will allow only one reminder.

### Why hooks will not ship in the Claude plugin

Putting Stepper hooks in this repository's plugin `hooks/hooks.json` would enable them for every user of every promoted skill in the bundle. That is broader than installing Stepper and would make independent use harder.

Skill-frontmatter hooks start too late for fresh-session recovery and proactive capture, and Cursor does not use them as its native hook source. `install-hooks` therefore merges Stepper entries into the user's Claude and Cursor hook settings using absolute paths. Re-running it will be safe.

Without hook installation, explicit capture and every CLI operation still work. Proactive suggestions, automatic recovery injection, and stop reminders do not.

## Reminder policy

The deterministic core generates compact reminders, for example:

> Stepper: AC-3 active; AC-4 pending. Do not conclude the tracked work until both are resolved or explicitly deferred.

A reminder will be emitted only when:

- A session starts or resumes with outstanding tracked work.
- Context has just been compacted.
- The active item was verified and another pending item becomes active.
- The agent is about to stop after working on tracked work while commitments remain.
- The agent claims tracked work is complete while commitments remain.

Stepper will not interrupt unrelated questions, paused contexts, or ordinary tool calls. Stop continuations are capped at one for a generation.

Distinguishing tracked work from an unrelated turn will use conservative prompt and response patterns. This is not semantically perfect. The skill instruction remains the primary rule: tracked work is not complete until `stepper status` reports closure. The hook is a deterministic backstop for the common forget-the-next-item failure.

## Responsibility matrix

| Behavior | Deterministic core | Agent | Platform hooks |
| --- | --- | --- | --- |
| Persist, load, lock, and atomically save state | Yes | No | No |
| Assign identifiers and enforce transitions | Yes | No | No |
| Select the next item and compute progress | Yes | No | No |
| Require evidence to verify | Enforces presence | Judges adequacy | No |
| Handle corrupt or missing state | Yes | Reports CLI errors | Fail open |
| Pause, resume, block, defer, cancel, and close | Yes | Invokes requested command | Honors paused state |
| Interpret natural-language requests | No | Yes | No |
| Extract clearly formatted outstanding lists | Yes | Fallback for ambiguous text | Supplies assistant text |
| Decide that an ambiguous list is a commitment | No | Yes | No |
| Ask before activating a suggestion | Records decision | Yes | Flags candidate only |
| Perform and verify implementation work | No | Yes | No |
| Generate reminder text | Yes | Acts on it | Injects at supported boundaries |
| Restore after a new session | Reads disk | No | Session-start injection |
| Restore after compaction | Reads disk | No | Platform-specific injection |
| Prompt the user directly | No | Yes | Unsupported |

## Testing

The deterministic core will use Python's `unittest` and temporary directories. Tests will cover:

- State creation and atomic persistence
- Item activation and verification
- Invalid transitions
- Evidence requirements
- Blocked and deferred items
- Pause and resume
- Fresh-process restoration
- Multiple contexts
- Duplicate operations
- Corrupt-state quarantine
- Completion detection
- Reminder generation
- Candidate deduplication and decline handling
- Hook failures without state corruption

A scripted lifecycle test will use four acceptance criteria:

1. AC-1 and AC-2 are already satisfied.
2. The parser detects AC-3 and AC-4 as outstanding.
3. The same candidate is offered once, accepted, and captured.
4. AC-3 remains active through an extended sequence of simulated hook calls.
5. AC-3 cannot be verified without evidence.
6. Verifying AC-3 activates and reminds about AC-4.
7. Verifying AC-4 closes the context.
8. A fresh process restores the state throughout.
9. Pausing and unrelated questions suppress reminders.
10. A failed hook leaves state unchanged.

Hook fixtures prove adapter behavior against documented payloads. They will not be described as end-to-end platform tests. Separate manual integration tests will exercise actual Cursor and Claude Code hook execution, session restart, and compaction.

## Repository changes after approval

Implementation will add the Stepper files above and the promotion bookkeeping required by this repository:

- Top-level `README.md`
- `skills/productivity/README.md`
- `.claude-plugin/plugin.json`
- `docs/productivity/stepper.md`
- A changeset

No unrelated skill or repository-wide runtime dependency will be changed.

## Known limitations

- Hooks cannot ask the user a yes/no question. The agent must make the offer.
- Cursor cannot inject Stepper state into the model at the exact compaction boundary. The next tool result or stop follow-up is the closest documented mechanism.
- Cursor `sessionStart` does not cover compaction.
- Cursor user hooks do not run in cloud agents.
- Skill-frontmatter hooks cannot provide fresh-session recovery before invocation.
- Conservative keyword classification can miss unusual wording or produce one unnecessary follow-up.
- Unit and fixture tests do not establish real platform integration.

## Approval gate

No implementation should begin until this architecture is approved. Approval includes the following choices:

- Python 3 standard library, with no runtime dependencies
- One JSON state file per context under a locally excluded `.stepper/`
- Explicit user-level hook installation rather than plugin-wide hooks
- Deterministic candidate parsing with no per-message LLM evaluation
- One bounded reminder at meaningful lifecycle boundaries
