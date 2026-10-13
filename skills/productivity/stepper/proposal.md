# Stepper Architecture Proposal

Status: v1 approved and implemented. The hierarchy revision is approved, including the focus, descent, and depth-independent traversal clarifications below.

The deterministic architecture in this document is the implementation contract. The notes below record behavior that live Cursor execution did not confirm. The hierarchy section is a proposal, not a change to the shipped v1 contract.

## Implementation notes

Cursor `agent --print` 2026.10.01, in a trusted workspace whose hooks only logged events, fired `sessionStart`, then `preToolUse`, then `postToolUse` for one shell command. It did not fire `afterAgentResponse` or `stop`.

In the IDE session that built Stepper, project hooks logged `preToolUse` and `postToolUse` while the turn was still open. `afterAgentResponse` did not run between those tool calls.

A later read of that IDE log showed the turn ending as the last `postToolUse`, then `afterAgentResponse` for the same generation, then `stop`. The `stop` payload had a new generation id, `loop_count` 0, and no response text. A later `postToolUse` in the generation that produced the message was not observed, so the offer does not depend on one. Cursor stores the message in `afterAgentResponse` and offers from `stop`. The CLI run still did not fire either event, so that offer path is fixture-tested. Claude `Stop` reads `last_assistant_message` and creates a session only when that message contains a new candidate.

The session key is injected when a prompt addresses Stepper, and again on session start when that session holds a lease. It is not repeated on every later prompt. Cursor cannot attach context in `beforeSubmitPrompt`, so the key is carried on the next `postToolUse` instead.

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

- `sessionStart` can add `additional_context` when a new composer conversation is created. It does not fire after compaction. Its output may also set environment variables for later hook executions.
- `afterAgentResponse` receives completed assistant text but has no documented response fields. It can detect and record candidates, but cannot prompt the user or inject agent context.
- `stop` can return `followup_message`, which Cursor submits as another user message. Its input does not contain the assistant response text. This is an additional agent turn.
- `preCompact` is observational. It can show a user message but cannot alter compaction or add agent context.
- `postToolUse` can add `additional_context` after a tool result, so the model can use it in the reply it is already producing.
- `beforeSubmitPrompt` can inspect or block a prompt. It cannot rewrite the prompt or add model context.
- Stop follow-ups default to a limit of five per script and can be configured lower.
- Common hook input includes `conversation_id`, `generation_id`, and `hook_event_name`. Cursor event names are camelCase (`stop`, `sessionStart`).
- User-level hooks do not run in Cursor cloud agents. Project hooks do.

Cursor can import Claude Code hooks from Claude settings when third-party imports are enabled. It maps the common lifecycle events and treats a Claude `Stop` block as a Cursor follow-up. Native Cursor configuration is still required for `afterAgentResponse`.

### Claude Code

Claude Code loads hooks from settings, a plugin's `hooks/hooks.json`, and invoked skill frontmatter.

- Plugin hooks register whenever the plugin is enabled.
- Skill-frontmatter hooks register only after that skill is invoked and remain for the rest of the session.
- `SessionStart` supports `startup`, `resume`, `clear`, `compact`, and `fork`. Its output can add context for Claude. Resume and compaction keep the same session identity for an ongoing conversation.
- `Stop` receives `last_assistant_message` and `stop_hook_active`. `additionalContext` continues the conversation. That continuation is an additional agent turn. A blocking decision does the same and is presented as a hook error.
- `PostToolUse` can add `additionalContext` during the turn, before the next model call.
- `PreCompact` runs before compaction and can block it.
- `PostCompact` is available for side effects but cannot inject or control the next turn.
- `MessageDisplay` can alter display text only. It does not alter the transcript or what Claude sees.
- Common input includes `session_id`. Claude event names are PascalCase (`Stop`, `SessionStart`).
- Command hooks cannot open an interactive terminal prompt.

Neither platform provides a hook that can directly ask the user whether a candidate list should be tracked.

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
├── contexts/
│   └── <context-id>.json
├── sessions/
│   └── <platform>_<session-id>.json
├── suggestions.json
└── quarantine/
```

There is no global `current` pointer and no shared `runtime.json`. A single pointer would make every session in the repository read and update the same context.

- One JSON file represents one tracking context.
- One session file represents one Cursor conversation or Claude Code session. Concurrent sessions write different files.
- `suggestions.json` stores repo-level candidate hashes and their offer state.
- Installation will add `.stepper/` to `.git/info/exclude`, not the repository's committed `.gitignore`.
- Creation will fail rather than overwrite an existing context file.
- Context and suggestion writes use a lock, a temporary file, and an atomic rename.
- Session filenames use only letters, digits, dot, underscore, and hyphen. The file stores the canonical session key.

Each item will contain:

- Stable identifier
- Description
- Completion criteria
- Status
- Optional evidence string
- Optional blocked reason
- Stable order

Source identifiers such as `AC-3` will be preserved. Otherwise the CLI will assign monotonic identifiers and never reuse them.

## Session leases

A context has at most one lease:

```json
{
  "session_key": "cursor:<conversation_id>",
  "acquired_at": "2026-10-13T14:00:00Z"
}
```

Claude keys use `claude:<session_id>`. Hooks read the platform session id from their payload. The CLI never infers a session from the most recent hook, the working directory, or an ambient "current" file.

Rules:

- `capture` creates a context and leases it to the `--session` that called it.
- Mutating commands require `--session`. The session must already have a session file written by a hook. The CLI rejects an unknown or invented session key.
- Only the lease holder can change that context, receive its reminders, or run its compaction reinjection.
- A session with no lease does not attach itself because another context exists.
- `attach` acquires a context only when its lease is empty.
- `attach --take` is the only way to move a live lease. The agent may pass `--take` only after the user explicitly asks to continue that tracked work in this session.
- `detach` and `sessionEnd` release the lease when the ending session holds it. They do not delete or rewrite items.
- A crashed or killed session keeps its lease. There is no timeout. A long-lived session must not lose its lease because a clock expired, and a new session must not inherit it by guessing. The user moves it with `attach --take`.
- `status` without `--session` is a read-only inventory of contexts, leases, and corrupt files. It attaches nothing.
- `status --session <key>` reports that session's lease and suggestion state.

Tradeoff: the same conversation keeps its work across turns, Claude resume, and compaction, because those keep the same session id. A new conversation in the same repository does not automatically resume that work. Resuming there is an explicit attach. That is the safe choice. Automatic attach of "the" active context would be convenient and would also let two concurrent sessions interfere.

Hook sessions are registered lazily. An unrelated conversation creates no session file and receives no injected text. `beforeSubmitPrompt` or `UserPromptSubmit` creates the session file and injects one session-key line only when the prompt addresses Stepper, or when that session already holds a lease. Candidate detection may also create the session file when it stores a candidate.

Declines and acceptances are repo-level, so one conversation's decision is not offered again by another. An in-flight candidate that has already been offered is not offered a second time in a different session. The user can still capture it explicitly.

## Corrupt state

A file is corrupt when it exists but is not valid JSON, or is valid JSON that does not match the expected schema. A missing file is not corrupt.

On a corrupt read:

1. Leave the original file at its original path, unmodified.
2. Copy its original bytes into `.stepper/quarantine/<name>-<timestamp>.json`.
3. If that copy fails, still leave the original untouched.
4. Exit with an error that names both paths.

No command repairs, renames, truncates, or deletes the corrupt file. No command creates a replacement context for that id, clears its lease, or chooses a fresh id in order to continue. `capture` of a corrupt context id fails. Hooks write nothing except a successful quarantine copy, inject nothing, and do not create a context.

The id becomes usable again only after the user replaces or removes that file outside Stepper. There is no `recover` command, because an automatic or one-flag replacement is the silent-tracking failure this rule exists to prevent.

Partial writes are avoided by the temp-file rename. Readers either see the previous valid file or the completed new file.

## State machine

Supported statuses:

- `pending`: outstanding and actionable
- `active`: the single item currently being addressed
- `blocked`: waiting for a stated dependency or condition
- `verified`: recorded as complete after a non-empty evidence string was stored
- `deferred`: explicitly postponed
- `cancelled`: explicitly removed from scope

Legal transitions:

| From | To |
| --- | --- |
| `pending` | `active`, `verified`, `deferred`, `cancelled` |
| `active` | `pending`, `blocked`, `verified`, `deferred`, `cancelled` |
| `blocked` | `pending`, `active`, `deferred`, `cancelled` |
| `deferred` | `active`, `cancelled` |
| `verified` | none |
| `cancelled` | none |

`focus` is the transition to `active` from `pending`, `blocked`, or `deferred`. The previous active item returns to `pending`. `unblock` is the transition from `blocked` to `pending` when the user wants it actionable but not active.

Only one item may be active. Verifying the active item activates the next `pending` item in stable order. Blocked and deferred items are skipped. Verifying a pending item does not change which item is active.

A context is complete when every item is either verified or cancelled and at least one item is verified. Cancelled work is out of scope, not satisfied. Deferred work remains incomplete. Blocked work remains outstanding.

Pausing affects the context, not item statuses. Hooks for that lease stay quiet until resume. `close` drops the lease and marks the context closed without marking unfinished items verified.

### Verification evidence

`verify` checks structure only:

- The transition is legal.
- `--evidence`, after trimming, is a non-empty string.
- The string is stored exactly as supplied, apart from trimming the ends.

The CLI does not run tests, inspect the repository, score the explanation, or decide whether the statement is true. A false or irrelevant sentence passes. Adequacy belongs to the agent: it may supply evidence only for a criterion it has actually established. `SKILL.md` will say that directly. The evidence field is an audit note, not a proof.

## CLI

The public verbs stay narrow because users speak in those verbs, and because `verify` and `block` carry required fields. Internally they call one transition function. There are not separate state machines per verb.

Context and session:

- `capture --session S` creates a context, adds its initial items, leases it to `S`, and focuses the first pending item
- `add --session S` appends items to the context `S` holds
- `status [--session S]`
- `attach --session S <context> [--take]`
- `detach --session S`
- `pause --session S`
- `resume --session S`
- `close --session S`

Item transitions:

- `focus --session S <id>`
- `verify --session S <id> --evidence TEXT`
- `block --session S <id> --reason TEXT`
- `unblock --session S <id>`
- `defer --session S <id>`
- `cancel --session S <id>`

Suggestions and setup:

- `decline --session S <hash>`
- `hooks install {cursor|claude}`
- `hooks uninstall {cursor|claude}`
- `hooks status`
- `hook --platform {cursor|claude} --tag stepper` for hook entry only

Removed from the previous draft:

| Removed | Reason |
| --- | --- |
| `start` | `capture` creates the context. An empty context has nothing to remind about. |
| `next` | `status` includes the active item and the next pending item. |
| `activate`, `resume-item` | `focus` is the only transition to `active`. |
| `stop` | Renamed `close` so it is not confused with the hook event. |
| `detect`, `suggest` | Detection and offer state stay inside `hook`. |
| `install-hooks` | Split into per-platform `hooks` subcommands. |

Not added: import, export, rename, edit, reorder, repair, or a generic `set-status` command. A generic setter would widen the surface without making the transitions more deterministic.

Duplicate calls are idempotent when the requested end state already holds. They fail when repeating them would drop evidence, a reason, or an item.

## Proactive capture

Candidate detection is deterministic and conservative.

The parser accepts a list only when nearby text identifies outstanding work, such as remaining acceptance criteria, unresolved findings, failures, or TODOs. It recognizes Markdown checklists, numbered criteria, and explicit status words. It ignores checked or satisfied items, illustrative lists, and unqualified numbered lists.

The normalized list is hashed. Repo-level suggestion state moves through:

```text
unseen -> offered -> accepted
                 \-> declined
```

`offered` is recorded when Stepper first injects an offer instruction, so the same hash does not produce another injection or another turn. A decline is permanent for that hash. Acceptance stores the hash on the new context. Hooks never call `capture`. The agent asks, then calls `capture` only after the user accepts.

A session that already holds a lease does not get an offer. The candidate is stored and waits until that context is closed. Paused leases are also quiet. Lists the parser does not recognize are captured only when the user asks. Stepper does not spend a model call to classify them.

### When a suggestion costs an extra turn

An extra agent turn means the hook submits work after the agent has already finished responding:

- Cursor `stop` returns `followup_message`.
- Claude `Stop` returns `additionalContext`.

`PostToolUse` context is not an extra turn. It arrives before the next model call inside the turn the agent is already running.

| Situation | Extra turn | Injection |
| --- | --- | --- |
| The candidate appears in assistant text and a later tool call still happens in that turn | No | One short `postToolUse` / `PostToolUse` reminder. The agent can include the offer in the reply it is about to write. |
| The candidate appears only in the final assistant message | Yes, one | `stop` / `Stop` asks the agent to offer the list. This is the "reported AC-3 and AC-4, then stopped" case. |
| That hash is already `offered`, `accepted`, or `declined` | No | None |
| This session holds a lease, or that lease is paused | No | None |
| The user prompt is unrelated and no new hash was detected | No | None |

The in-turn reminder and the stop follow-up are mutually exclusive. Once either is sent, the hash is `offered`. If the model ignores the in-turn reminder, Stepper does not spend a second turn to force the question.

Tradeoff: the closing-message case needs the extra turn because `afterAgentResponse` cannot change a message that has already completed, and Cursor's `stop` input does not include that text. The earlier `afterAgentResponse` hook stores it for the stop decision. Folding the offer into an in-progress turn is preferred whenever a later tool call gives a place to inject it.

Suggestion text does not repeat the list. The list is already in the conversation. The injection names the hash and the count, and tells the agent to ask once without capturing.

Tracked-work reminders are separate and use the compact form:

> Stepper: AC-3 active; AC-4 pending. Do not conclude the tracked work until both are resolved or explicitly deferred.

Those reminders go only to the lease holder, and only when:

- that session starts or resumes with outstanding work
- that session has just been compacted
- `verify` activates the next pending item
- the lease holder is stopping after tracked work while commitments remain
- the lease holder claims the tracked work is complete while commitments remain

They are not injected on ordinary tool calls, unrelated questions, or paused contexts. A stop continuation for tracked work is capped at one per generation.

Distinguishing tracked work from an unrelated turn uses conservative prompt and response patterns. That classification can miss unusual wording. The skill rule remains primary: tracked work is not complete until `status` reports closure. The hook is the backstop for forgetting the next item.

## Hook installation

Installing the skill does not register hooks. Hooks are optional and per platform. With no platform argument, `hooks install` changes nothing.

```text
stepper hooks install cursor
stepper hooks install claude
stepper hooks uninstall cursor
stepper hooks uninstall claude
stepper hooks status
```

Defaults:

- Cursor: `~/.cursor/hooks.json`
- Claude Code: `~/.claude/settings.json`

Each installed command includes `--tag stepper` and `--platform cursor` or `--platform claude`. Uninstall removes a hook entry only when its command contains that tag and platform. It does not remove neighboring entries.

Install and uninstall:

1. Refuse if the target exists and is not valid JSON. Do not rewrite it.
2. Copy the original bytes to `~/.stepper/backups/<platform>-<timestamp>.json` before the first write.
3. Change only that platform's file.
4. Preserve every key and hook entry that is not a Stepper entry.
5. Append a Stepper entry only when the same command, event, and matcher are absent.
6. On uninstall, delete a file only when Stepper created it and no non-Stepper content remains. Remove an empty `hooks` key only when Stepper added that key and it is empty again.
7. Record the target path in `~/.stepper/hook-install.json`.

Uninstall edits the current file. It does not restore a backup over later user edits. The backup is there if a person wants the previous bytes.

Tradeoff: rewriting through a JSON parser preserves unrelated settings semantically and can change whitespace or key order. JSON comments are not accepted; a file that does not parse is left untouched.

Runtime independence: `--platform claude` exits immediately when `hook_event_name` is a Cursor camelCase event, and `--platform cursor` does the reverse. Installing Claude hooks therefore does not also drive Cursor when Cursor imports `~/.claude/settings.json`. Generation deduplication remains for the case where the same platform reports one event twice.

These hooks are not added to the Claude plugin. Plugin hooks would run for every promoted skill. Skill-frontmatter hooks start too late for a fresh session and are not Cursor's hook source.

Without the matching platform install, explicit CLI use still works. Proactive offers, lease reminders, and compaction reinjection do not run on that platform.

### Claude Code events

1. `SessionStart` for `startup`, `resume`, and `compact`: if this session holds a lease with outstanding work, inject one reminder and the session key.
2. `UserPromptSubmit`: register the session when the prompt addresses Stepper or the session holds a lease. Record the prompt class. Inject the session key only in those cases.
3. `PostToolUse`: deliver at most one suggestion reminder or one post-compaction reminder for this session.
4. `Stop`: apply the extra-turn rules above. Exit with no output when paused, unrelated, already continued (`stop_hook_active`), or already offered.
5. `PreCompact`: set this session's compaction marker. Do not block compaction.
6. `SessionEnd`: release the lease if this session holds it.

### Cursor events

1. `sessionStart`: same lease-holder reminder for a new composer. This does not cover compaction.
2. `beforeSubmitPrompt`: same lazy session registration. No model context is added, because this event cannot add any.
3. `afterAgentResponse`: store the assistant text and run detection. No response fields are emitted.
4. `postToolUse`: one suggestion reminder, or one post-compaction reminder, then clear that session's marker.
5. `stop`: one follow-up at most (`loop_limit: 1`), using the text stored by `afterAgentResponse`.
6. `preCompact`: set this session's marker. Do not show a user toast.
7. `sessionEnd`: release the lease if this session holds it.

## Responsibility matrix

| Behavior | Deterministic core | Agent | Platform hooks |
| --- | --- | --- | --- |
| Persist, load, lock, and atomically save state | Yes | No | No |
| Bind a session to one context and reject other writers | Yes | Passes the hook-registered session key | Supplies the platform session id |
| Assign identifiers and enforce transitions | Yes | No | No |
| Select the next item and compute progress | Yes | No | No |
| Require non-empty verification evidence | Structural check only | Decides whether the claim is actually true | No |
| Preserve corrupt files and refuse replacement state | Yes | Reports the CLI error | Fail open after a quarantine copy |
| Pause, resume, block, defer, cancel, and close | Yes | Invokes the requested command | Honors the lease and paused flag |
| Interpret natural-language requests | No | Yes | No |
| Extract clearly formatted outstanding lists | Yes | Fallback for ambiguous text | Supplies assistant text |
| Decide that an ambiguous list is a commitment | No | Yes | No |
| Ask before activating a suggestion | Records offered, accepted, and declined | Asks, then captures only after a yes | Injects one offer instruction |
| Perform the implementation work | No | Yes | No |
| Generate reminder text | Yes | Acts on it | Injects it only for the lease holder |
| Restore the same session after resume or compaction | Reads disk | No | Injects for that session id |
| Continue work in a different session | Transfers the lease only on `attach --take` | Asks the user before passing `--take` | Does not auto-attach |
| Prompt the user directly | No | Yes | Unsupported |

## Testing

The deterministic core will use Python's `unittest` and temporary directories. Tests will cover:

- State creation and atomic persistence
- Session leases, including two concurrent sessions and a rejected cross-session write
- `attach`, failed attach of a live lease, and `attach --take`
- Lease release on detach and session end, without item changes
- Item focus, verification, and invalid transitions
- Rejection of empty or whitespace-only evidence, and acceptance of an unchecked non-empty string
- Blocked and deferred items
- Pause and resume
- Restoration by the same session key in a fresh process
- No automatic attach for a new session key
- Multiple contexts
- Duplicate operations
- Corrupt input left byte-for-byte in place, with no replacement context
- Completion detection
- Reminder generation
- Suggestion offer, decline, and one-turn behavior
- Hook install and uninstall that preserve unrelated JSON settings
- A failed hook that does not change context bytes

A scripted lifecycle test will use four acceptance criteria:

1. AC-1 and AC-2 are already satisfied.
2. The parser detects AC-3 and AC-4 as outstanding.
3. A final-message candidate produces one offer turn, and the same hash produces no second offer.
4. Acceptance captures a context leased only to that session.
5. AC-3 remains active through an extended sequence of simulated hook calls.
6. AC-3 cannot be verified without evidence. Non-empty evidence is stored without a correctness check.
7. Verifying AC-3 activates and reminds about AC-4.
8. Verifying AC-4 closes the context.
9. A second session cannot mutate the context or receive its reminders.
10. The same session key restores the state in a fresh process.
11. Pausing and unrelated questions suppress reminders.
12. A failed hook leaves context bytes unchanged.

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
- A candidate that appears only in the final message costs one extra agent turn. That is the earliest reliable offer after the message has completed.
- An in-turn offer reminder can be ignored by the model. Stepper will not add a follow-up turn to correct that.
- Cursor cannot inject Stepper state into the model at the exact compaction boundary. The next tool result, or one stop follow-up if no tool follows, is the closest documented mechanism.
- Cursor `sessionStart` does not cover compaction.
- Cursor user hooks do not run in cloud agents.
- A new conversation does not inherit another conversation's lease.
- A crashed session keeps its lease until the user explicitly takes it.
- Skill-frontmatter hooks cannot provide fresh-session recovery before invocation.
- JSON hook installation preserves unrelated settings semantically and may change formatting.
- Conservative keyword classification can miss unusual wording or produce one unnecessary follow-up.
- Unit and fixture tests do not establish real platform integration.

## Hierarchy

v1 is a flat list: one active item, and `order` is that item's place in the single list. An item has no parent. The identifier grammar accepts `AC-3` and `item-1`. It rejects `AC-3a`, `AC-3b`, and `AC-3b-1`.

v2 adds sub-steps without turning Stepper into a planner. The user names the parent. The CLI stores the link, checks depth, and calculates progress. Nothing walks a description and invents children.

### Data model

Each item gains one field:

```json
"parent_id": null
```

`null` is a top-level item. A string is the id of another item in the same context. Children stay in the same `items` array. There is no nested JSON tree on disk, so a later depth increase does not move records or rename files.

`order` becomes the order among items with the same `parent_id`. Existing flat items already have `parent_id` absent and an `order` that matches their list position. On read, a missing `parent_id` is `null`. The context `version` stays `1`. A v1 file is valid. The next mutating command writes `parent_id` on every item. `status` does not rewrite the file. There is no migration command and no new directory.

Validation:

- `parent_id` is `null` or the id of an item in this context.
- An item is not its own parent.
- Walking parents never repeats an id.
- Ids are unique in the context.
- Depth is the number of parent hops. A top-level item has depth 0. `AC-3b` under `AC-3` has depth 1. `AC-3b-1` under `AC-3b` has depth 2.

`MAX_DEPTH = 2` is the only depth limit. Depth 2 is a top-level item plus two levels of children, which is the `AC-3 → AC-3b → AC-3b-1` example. A command that would create depth 3 fails with:

```text
cannot add AC-3b-1-a under AC-3b-1: depth 3 exceeds MAX_DEPTH 2
```

The item is not added. Nothing is reparented, flattened, or dropped. Raising `MAX_DEPTH` later is a one-constant change. Stored `parent_id` values already allow the deeper chain.

### Identifiers

The identifier grammar becomes:

```text
^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+$
```

That accepts the ids v1 already stores (`AC-3`, `item-1`) and the ids this revision has to preserve (`AC-3a`, `AC-3b`, `AC-3b-1`). The same pattern parses `AC-3b-1: description`, so the label is not cut at `AC-3`.

The id does not encode the parent. `AC-3b-1` added without `--parent` is top-level. `add --parent` is the only way to place it. Generated ids stay `item-N` from `next_seq`, and only when the user supplies no id. The CLI does not invent `AC-3a` from a parent's name.

### Command

`add` grows one flag:

```text
add --session S --parent AC-3 --item "AC-3b: check the reset token" --item "AC-3a: check the template"
```

`--parent` may be omitted. Those items stay top-level, as `add` works today. `capture` does not take `--parent`. A new context is still a flat list of top-level items.

`add --parent` appends pending children in the order written. It does not change which item is active. It fails when the parent is missing, verified, or cancelled, when an id is duplicated, or when the new depth would exceed `MAX_DEPTH`.

Agent phrasing maps onto that one flag:

| Request | Command |
| --- | --- |
| Track these as sub-steps of AC-3 | `add --parent AC-3` |
| Add these under AC-3b | `add --parent AC-3b` |
| Mark AC-3b-1 verified | `verify AC-3b-1 --evidence TEXT` |
| Show overall progress | `status` |
| Show the full tree | `status --tree` |
| What's left to finish AC-3 | `status --tree`, then the AC-3 subtree |

Hooks do not learn a new event. They do not receive the tree. Proactive detection still stores a flat candidate. Hierarchy starts only when the user names a parent and the agent calls `add --parent`.

### Active item

At most one item is `active`.

Adding children leaves the active item where it is. If `AC-3` is active and gains children, `AC-3` stays active until a later `focus` or `verify`. That is the one case an item with unresolved children is active. The status path still starts at `AC-3`, so the parent commitment stays visible.

`focus` of a leaf demotes the previous active item to `pending` and activates the leaf. The parent is not given a second status. Its place in the work is the ancestor path.

`focus` of an item that still has a pending, active, or blocked descendant fails before any status changes:

```text
AC-3 has unresolved children; focus a leaf
```

The CLI does not choose a child on the user's behalf.

An active item must not sit under a deferred ancestor. `focus` on a descendant whose ancestor is `deferred` returns every deferred ancestor on that path to `pending`, then activates the requested leaf. Returning to `pending` drops no evidence and no blocked reason, because a deferred item has neither. The command does not leave the ancestor deferred, and it does not leave the ancestor active above the child. If the focus itself fails because the target has unresolved children, the ancestors stay deferred.

Verifying the active item chooses the next active item by walking parent links. The walk is the same at every depth. `MAX_DEPTH` is checked only when an item is added. A deeper tree, loaded or produced by raising the constant, uses this same walk.

1. Scan the finished item's siblings in `order`, skipping the finished item. A `pending` sibling with no children becomes active. A `pending` sibling with unresolved descendants is entered, and the same rule selects inside it. The branch is not skipped because it has children.
2. When no sibling branch is selected and every descendant of the parent is verified or cancelled, the parent becomes `active` if it is `pending`. The parent is not verified.
3. When the parent does not become active, repeat the same walk from the parent.
4. `blocked` and `deferred` nodes are not selected and are not entered. That matches the flat list, which also skips them.

So finishing `AC-3b-1` makes `AC-3b` active when `AC-3b` has nothing else outstanding. Finishing the last child of `AC-3` makes `AC-3` active. `AC-4` waits until `AC-3` itself is verified, deferred, or cancelled. Verifying a non-active item still does not move the active item.

A parent may be verified from `pending` or `active` once it is eligible. Eligibility means every descendant is `verified` or `cancelled`. The command still requires non-empty `--evidence`. Child evidence is not copied up.

These descendants keep the parent ineligible:

- `pending`, `active`, and `blocked`
- `deferred`

The error names the ids:

```text
cannot verify AC-3 until AC-3b is resolved
```

`cancelled` and `verified` descendants do not block the parent. A parent with only cancelled children can be verified, or cancelled, like any other eligible item.

`defer` and `cancel` of a parent do not change descendants. They fail while any descendant is `pending`, `active`, or `blocked`, and they name those ids. The user resolves those descendants first. A parent may be deferred or cancelled while its remaining descendants are already `verified`, `cancelled`, or `deferred`.

`block` stays legal only from `active`. It does not cascade. After the active item is blocked, no other item becomes active, which is the v1 rule.

Verified and cancelled items stay terminal. v2 does not un-verify an item or strip its evidence. Reopening means a `deferred` item is focused, or a `blocked` item is unblocked or focused. That descendant is outstanding again, so a parent that was only eligible returns to ineligible. If that parent was the active item, `focus` on the child demotes the parent to `pending`. A verified parent rejects `add --parent` and rejects any transition of its descendants.

### Progress

Overall progress counts top-level items only. A top-level item is resolved when its own status is `verified` or `cancelled`. Finished children do not mark the parent resolved and are not added into the overall numerator.

Each parent separately reports direct children: resolved direct children over direct children. Grandchildren appear on their own parent. They are not added again to the grandparent's fraction or to the overall fraction.

`status` adds:

```json
"progress": {
  "top_level": {"resolved": 0, "total": 2},
  "active_path": ["AC-3", "AC-3b", "AC-3b-1"]
}
```

`active_path` is the active item and its ancestors, root first. A flat context has a one-element path. `status` without `--session` adds the same `top_level` counts to each context summary and omits the path.

`status --tree` adds a nested `tree` built from `parent_id` and sibling `order`. Each node has `id`, `status`, `children_resolved`, `children_total`, and `children`. The concise status omits `tree`.

A flat context's reminder text stays the v1 sentence. A context that has any child uses one shorter reminder: the active path, the top-level counts, and the direct-child counts of the active item's parent when that parent exists. It does not list every descendant. Stop hooks and session-start hooks keep using that reminder, so hierarchy does not add a tree to the prompt.

Context completion is unchanged and still looks at every item: each item is `verified` or `cancelled`, and at least one is `verified`. The parent gate makes that equivalent to every top-level item being resolved, because a parent cannot be verified or cancelled while a required descendant is open.

### Decisions that need to stay visible

- An active item may temporarily have unresolved children, because `add` must not move focus.
- The CLI then makes an eligible parent active so the branch is verified before the next top-level item. That parent has children, and it is active only because those children are resolved.
- `focus` reactivates a deferred ancestor to `pending` before activating the requested leaf. An active child under a deferred parent is not a stored state.
- Sibling selection enters a pending branch that still has unresolved children. Traversal does not contain a depth cutoff. Raising `MAX_DEPTH` needs tests at the new depth, not a new walk.
- There is no un-verify. Reopening is the existing return from `deferred` or `blocked`, plus the ancestor reactivation above.
- A deferred child blocks parent verification. Cancelling the child is the way to remove it from scope.
- `item-N` is the generated id. A hierarchical id appears only when the user supplies it.
- Detection stays flat. "Track these as sub-steps of AC-3" is an explicit `add`, not a parsed capture.

## Approval gate

This revision was approved before implementation. The shipped choices are:

- Python 3 standard library, with no runtime dependencies
- One JSON state file per context under a locally excluded `.stepper/`
- One lease per context, with no implicit session attach
- Explicit, reversible, per-platform user-level hook installation
- Deterministic candidate parsing, with one extra turn only when the candidate is in the final message
- Non-empty evidence as a structural check
- Corrupt files preserved in place and never silently replaced

## Hierarchy approval gate

This hierarchy revision is approved. The approved choices are:

- `parent_id` on each item, with missing values read as `null` and no version bump
- `MAX_DEPTH = 2`, rejected rather than flattened
- User-supplied ids preserved, including `AC-3a` and `AC-3b-1`; generated ids remain `item-N`
- `add --parent` as the only new command surface
- One active item, unchanged by adding children, advancing to an eligible parent before the next branch
- Deferred ancestors return to `pending` when a descendant is focused
- Pending sibling branches are entered, and the walk has no depth cutoff
- Parent verification and parent cancel or defer blocked while a required descendant is open
- Overall progress counted from top-level items only, with `status --tree` for the rest
