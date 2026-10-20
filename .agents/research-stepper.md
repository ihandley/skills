# Stepper: smallest standards-based architecture

Research date: 2026-10-13. Primary sources only. This note does not implement Stepper.

> **Design note:** This research was started before the build prompt introduced
> “Architecture: Deterministic Core, Minimal Agent Involvement.” Its documented
> platform findings remain applicable. Earlier inferences that the agent should
> write state directly, that Stepper should support only one context, or that it
> must be model-invoked are superseded by the build requirements. The approved
> design must route every mutation through a deterministic CLI, support multiple
> tracking contexts, and choose invocation mode from the explicit-activation
> requirement and this repository's conventions.

**Smallest design compatible with the current build requirements:** one Agent Skill, a standard-library deterministic CLI, one state file per tracking context, and thin hook adapters. Register adapters at the smallest scope that can cover Claude `SessionStart` and `Stop`, and Cursor `sessionStart` and `stop`. Do not register per-tool, per-prompt, or compaction-blocking hooks unless an integration test demonstrates that a narrower recovery mechanism is insufficient.

The files are the memory. The CLI owns reads, validated transitions, locking, and atomic writes. Hooks call the CLI and format its read-only reminder output for the host. A failed hook must not mutate tracking state.

## Documented capability and inference

**Documented** below means the cited page says it. **Inference** means a design choice that follows from those statements but is not itself a platform guarantee. Nothing here was checked by running Cursor or Claude Code.

## What the Agent Skills spec provides

A skill is a directory with `SKILL.md` (YAML frontmatter plus Markdown), plus optional `scripts/`, `references/`, and `assets/`. Required frontmatter is `name` (1–64 chars, lowercase letters, digits, hyphens, no leading, trailing, or doubled hyphen, and it must match the parent directory) and `description` (1–1024 chars, what it does and when to use it). Optional spec fields are `license`, `compatibility` (max 500), `metadata` (string-to-string map), and experimental `allowed-tools`. The body has no required sections. Clients load `name` and `description` at startup, the body when the skill is activated, and other files only when needed. Keep `SKILL.md` under 500 lines. The spec defines no hooks, no state file, and no session store. Source: [Agent Skills specification](https://agentskills.io/specification), spec source [docs/specification.mdx](https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx).

Claude Code accepts that spec and adds its own frontmatter. `hooks`, `disable-model-invocation`, `user-invocable`, `paths`, and `context` are Claude Code fields. Packaging for claude.ai and the Skills API rejects any key outside `name`, `description`, `license`, `compatibility`, `metadata`, and `allowed-tools`. Source: [Extend Claude with skills](https://code.claude.com/docs/en/skills).

Cursor discovers skills from `.agents/skills/`, `.cursor/skills/`, `~/.agents/skills/`, `~/.cursor/skills/`, and the Claude and Codex skill directories. Its extra frontmatter is `paths`, `disable-model-invocation`, `icon`, `color`, and `metadata`. The Cursor skills page does not list a `hooks` field. A manually invoked skill attaches to one message; a Custom Mode keeps it for the session. Source: [Cursor Agent Skills](https://cursor.com/docs/skills).

## Invocation

Matt Pocock's repo splits skills on who can reach them. User-invoked means `disable-model-invocation: true` plus `policy.allow_implicit_invocation: false` in `agents/openai.yaml`, and a human-facing description. Model-invoked means omit both, and write a description that says when to use the skill. A user-invoked skill may call a model-invoked skill. It never calls another user-invoked skill. Every skill has `agents/openai.yaml` for Codex display metadata. Source: [mattpocock/skills `.agents/invocation.md`](https://github.com/mattpocock/skills/blob/main/.agents/invocation.md). This repo copies that rule in [`.agents/invocation.md`](./invocation.md).

**Inference:** Stepper should be model-invoked. Capture stays explicit because the skill body says so ("only when the user asks to track"), not because the model is forbidden to load the skill. Status, "what's left", pause, and resume have to be reachable without a slash command. A user-invoked skill would also keep Claude from registering skill-frontmatter hooks until the human types the name.

`/stepper` still works on both hosts: Cursor exposes `/skill-name`, and Claude Code turns the skill `name` into a slash command. Sources: [Cursor skills](https://cursor.com/docs/skills), [Claude skills](https://code.claude.com/docs/en/skills).

## State

There is no native commitment store in the Agent Skills spec, Cursor hooks, or Claude hooks.

Claude `scratchpad_dir` is a session temp directory (v2.1.257+). It is the wrong place for a list that must outlive the session. Source: [Hooks reference](https://code.claude.com/docs/en/hooks). `CLAUDE_PLUGIN_DATA` survives plugin updates, but it is plugin data, not a per-workspace file, and user `~/.claude/settings.json` is not read by cloud sessions. Source: [Hooks reference](https://code.claude.com/docs/en/hooks).

**Inference, following Planning with Files:** put one JSON file in the workspace, for example `.stepper/active.json`, and gitignore it. The agent writes it through the skill. Fields that match the brief: stable item id, description, completion criteria, status `pending` | `active` | `verified`, optional evidence, the active item id, and a mode `tracking` | `paused` | `stopped`. Record the host id that owns it (`session_id` on Claude, `conversation_id` on Cursor) so a second session can see that a list is already active. Refuse a new capture while mode is `tracking` unless the user explicitly replaces it. Do not commit it: two checkouts would fight over one live list.

Planning with Files stores `task_plan.md`, `findings.md`, and `progress.md` in the project, not in the skill directory. Hooks resolve the active plan from `PLAN_ID`, then `.planning/.active_plan`, then the newest plan directory, then a root `task_plan.md`. Isolated directories are how it runs two tasks at once. Source: [planning-with-files `SKILL.md`](https://github.com/OthmanAdi/planning-with-files/blob/master/skills/planning-with-files/SKILL.md). Stepper does not need that tree. One file and a refuse-to-overwrite rule covers "do not silently replace an active list." Parallel lists would be a second product.

## Reminder hooks

Hooks are host configuration. They are not part of the Agent Skills spec. A `SKILL.md` cannot by itself register Cursor hooks.

### Where hooks live

| Host | Location | When it runs |
| --- | --- | --- |
| Claude Code | `~/.claude/settings.json` | All projects on that machine. Cloud sessions do not read this file. |
| Claude Code | `.claude/settings.json` | One project. Can be committed. |
| Claude Code | `.claude/settings.local.json` | One project, gitignored when Claude writes it. |
| Claude Code | Plugin `hooks/hooks.json` | While the plugin is enabled. Bundled with the plugin. |
| Claude Code | Skill frontmatter `hooks` | From the moment the skill is invoked until that session ends, including later turns. Not before invocation, and not in a new process until the skill is invoked again. `once: true` is honored only here. |
| Cursor | `~/.cursor/hooks.json` | All local projects. Not available to cloud agents. Scripts run from `~/.cursor/`. |
| Cursor | `<repo>/.cursor/hooks.json` | That trusted workspace, including cloud agents. Scripts run from the repo root. |
| Cursor | Enterprise and team hooks | Dashboard or MDM. Enterprise cloud agents run team and enterprise hooks. |
| Cursor plugin | `hooks/hooks.json` or manifest `hooks` | Only a Cursor plugin (`.cursor-plugin/plugin.json`). An Agent Plugin (`plugin.json` at the root) packages skills and MCP servers, not hooks. |

Sources: [Claude hooks reference](https://code.claude.com/docs/en/hooks), [Cursor hooks](https://cursor.com/docs/hooks), [Cursor plugins reference](https://cursor.com/docs/plugins/building).

**Inference:** skill-frontmatter hooks cannot remind a fresh Claude session that already has a state file, because they are not registered yet. An always-on plugin hook or a project settings hook can. This repo's Claude plugin can ship `hooks/hooks.json`. A skills.sh install copies the skill only; Planning with Files documents the same split for its commands. Cursor skills.sh installs do not install hooks either. Cursor needs a project `.cursor/hooks.json` or a Cursor plugin. This repo is not a Cursor plugin.

### Claude Code events that matter

Common stdin fields include `session_id`, `transcript_path`, `cwd`, `hook_event_name`, and sometimes `permission_mode`. `transcript_path` can lag the live turn. Source: [Hooks reference](https://code.claude.com/docs/en/hooks).

Plain stdout is added to Claude's context only for `UserPromptSubmit`, `UserPromptExpansion`, `SessionStart`, and `PostModelSwitch`. Other events log stdout and do not treat it as context. `additionalContext` inside `hookSpecificOutput` is a system reminder, not a chat message. It is capped at 10,000 characters. Delivery:

| Event | Where the reminder lands |
| --- | --- |
| `SessionStart`, `SubagentStart` | Start of the conversation, before the first prompt |
| `UserPromptSubmit`, `UserPromptExpansion` | Beside the submitted prompt |
| `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch` | Beside the tool result |
| `Stop`, `SubagentStop` | End of the turn, and the conversation continues |
| `PostModelSwitch` | Next request after the switch |

`PreCompact` and `PostCompact` are not on that list. Source: [Hooks reference](https://code.claude.com/docs/en/hooks).

| Event | Matcher | Input that matters | Output that matters | Blocking |
| --- | --- | --- | --- | --- |
| `SessionStart` | `startup`, `resume`, `clear`, `compact`, `fork` | `source`. On `resume` or `fork` with at least one prior response, also staleness fields (v2.1.251+). | Plain stdout, or `hookSpecificOutput.additionalContext`. Also `initialUserMessage`, `sessionTitle`, `watchPaths`, `reloadSkills`. | Exit 2 does not block. Stderr is a hook-error notice. Claude does not see it. The session proceeds. |
| `PreCompact` | `manual` (`/compact`), `auto` | `trigger`, `custom_instructions` (`null` for auto) | `decision: "block"` plus `reason`. `systemMessage` and `continue` are discarded. | Exit 2 or `decision: "block"` blocks compaction. Proactive auto-compact is skipped. Compaction that was recovering from an already-returned context-limit error then fails the request. |
| `PostCompact` | `manual`, `auto` | `trigger`, `compact_summary` | None. JSON decision fields are discarded. | Cannot block or change the summary. |
| `UserPromptSubmit` | none; every prompt, including turns Claude starts itself | `prompt` | Plain stdout or `additionalContext`. `decision: "block"` rejects the prompt. | Exit 2 blocks the prompt. Default timeout 30s. On timeout the prompt still proceeds and the hook output is dropped, unless `onFailure` is `"block"`. |
| `Stop` | none | `stop_hook_active`, `last_assistant_message`, `background_tasks`, `session_crons`. Does not run on a user interrupt. API errors go to `StopFailure` instead, which ignores output. | `decision: "block"` plus `reason` continues the turn. `hookSpecificOutput.additionalContext` also continues it, labeled as feedback rather than an error. | Exit 2 continues, with stderr as the reason. After 8 consecutive continuations Claude stops anyway (`CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` raises it). The count resets when Claude calls a tool. |
| `TaskCompleted` | none | `task_id`, `task_subject`, optional `task_description` | Exit 2 refuses the task completion. | This gates Claude's task tool. It is not documented as a store that survives a new session. |

`SessionStart` with matcher `compact` is the documented way to put context back after compaction. The guide's example is a command whose stdout is added to Claude's context. Source: [Automate actions with hooks](https://code.claude.com/docs/en/hooks-guide). On startup, resume-at-launch, and `/clear`, `SessionStart` runs in the background, but Claude's first response waits for it. A prompt sent while it is still running does not reach Claude until the hooks finish. If `/clear` or a conversation switch happens while those hooks are still running, their output is dropped. `/resume` inside a session waits for the hooks. Source: [Hooks reference](https://code.claude.com/docs/en/hooks).

`/goal` is a built-in session-scoped prompt Stop hook. It keeps working until a condition, without a config file. It does not persist across conversations. Source: [Hooks reference](https://code.claude.com/docs/en/hooks).

Exit 0 with valid JSON applies the fields. Exit 2 blocks on events that can block, and JSON cannot override that block. Any other exit is a non-blocking error unless `onFailure` is `"block"` (v2.1.295+). `onFailure` has no effect on `Stop`. A missing script is a non-blocking error. On `Stop`, exit 2 with empty stdout and a "file not found" stderr is treated as non-blocking. Source: [Hooks reference](https://code.claude.com/docs/en/hooks).

### Cursor events that matter

Config is `hooks.json` with `"version": 1`. Command hooks get JSON on stdin and return JSON on stdout. Base input includes `conversation_id` (stable across turns), `generation_id` (changes every user message), `hook_event_name`, `workspace_roots`, `transcript_path` (null if transcripts are off), and `cursor_version`. `CURSOR_PROJECT_DIR` and `CLAUDE_PROJECT_DIR` are always set. Source: [Cursor hooks](https://cursor.com/docs/hooks).

| Event | When | Input beyond the base | Output | Blocking |
| --- | --- | --- | --- | --- |
| `sessionStart` | A new composer conversation is created. Not documented for resume or compaction. | `session_id` (same as `conversation_id`), `is_background_agent`, optional `composer_mode` (`agent`, `ask`, `edit`) | `additional_context` for the initial system context. `env` for later hooks in that session. | Fire-and-forget. The loop does not wait and does not enforce `continue` or `user_message`. `continue: false` does not stop session creation. |
| `sessionEnd` | Composer conversation ends. | `reason` (`completed`, `aborted`, `error`, `window_close`, `user_close`), `duration_ms`, `final_status` | Ignored. | Fire-and-forget. |
| `preCompact` | Before compaction. | `trigger` (`auto` or `manual`), token counts, `message_count`, `messages_to_compact`, `is_first_compaction` | Optional `user_message` shown to the user. | Cannot block or change compaction. |
| `stop` | Agent loop ends. | `status` (`completed`, `aborted`, `error`), `loop_count` | `followup_message`, submitted as the next user message when non-empty. | Default `loop_limit` is 5 auto follow-ups per script (`null` removes the cap). `loop_count` starts at 0. |
| `afterAgentResponse` | After an assistant message. | `text` | No output fields are documented. Matcher value is `AgentResponse`. | Observe only. |
| `beforeSubmitPrompt` | After send, before the backend request. Matcher value is `UserPromptSubmit`. | `prompt`, `attachments` | `continue` and, when blocked, `user_message` shown to the user. | `continue: false` blocks submission. No documented field injects model context. |
| `postToolUse` | After a successful tool call. | tool name, input, output | `additional_context` injected after the tool result. | Not a completion boundary. |

Exit 0 uses the JSON. Exit 2 denies, for permission-style hooks. Any other exit fails open unless `failClosed` is true. Invalid JSON blocks permission hooks even when `failClosed` is false. `followup_message` from several sources: the last response in priority order wins (Enterprise, Team, Project, User, so a lower-priority source overrides). Source: [Cursor hooks](https://cursor.com/docs/hooks).

Cloud agents run project command hooks, including `stop`, `preCompact`, `beforeSubmitPrompt`, and `afterAgentResponse`. They do not run `sessionStart` or `sessionEnd`. User hooks are absent. Prompt-based hooks do not run. Hooks do not run during an early read-only exploratory turn. Source: [Cursor hooks](https://cursor.com/docs/hooks).

**Inference from the fire-and-forget sentence:** Cursor documents `additional_context` on `sessionStart`, and also says the agent loop does not wait. Claude documents that the first response waits for `SessionStart`. Cursor does not. Treat Cursor's first-turn injection as a field that exists, not as a timing guarantee.

### One script, two JSON dialects

Cursor can load Claude settings hooks from `.claude/settings.local.json`, `.claude/settings.json`, and `~/.claude/settings.json` when third-party imports are on (the default). All sources run. Mapped names:

| Claude | Cursor |
| --- | --- |
| `SessionStart` | `sessionStart` |
| `SessionEnd` | `sessionEnd` |
| `PreCompact` | `preCompact` |
| `Stop` | `stop` |
| `UserPromptSubmit` | `beforeSubmitPrompt` |

A Claude `Stop` body of `{"decision":"block","reason":"..."}` becomes a Cursor `followup_message`. Exit 2 blocks on both. Response-format compatibility is documented for `PreToolUse` and for `Stop` / `SubagentStop`. It is not documented for `SessionStart` stdout or `additionalContext` becoming Cursor `additional_context`. `Notification` and `PermissionRequest` are not mapped. Skill-frontmatter hooks are not in the listed import paths. Source: [Third Party Hooks](https://cursor.com/docs/reference/third-party-hooks).

**Inference:** branch the script on `hook_event_name`. Claude `SessionStart` can print one plain line. Cursor `sessionStart` must print `{"additional_context":"..."}`. Claude `Stop` prints `additionalContext` or nothing. Cursor `stop` prints `followup_message` or `{}`. Do not assume a Claude settings hook injects session context inside Cursor.

## What to take from Planning with Files

Source of the behavior below: [SKILL.md](https://github.com/OthmanAdi/planning-with-files/blob/master/skills/planning-with-files/SKILL.md) and [inject-plan.sh](https://github.com/OthmanAdi/planning-with-files/blob/master/skills/planning-with-files/scripts/inject-plan.sh) on `master` (skill metadata version 3.10.0).

The canonical skill frontmatter registers `UserPromptSubmit`, `PreToolUse` (Write, Edit, Bash, Read, Glob, Grep), `PostToolUse` (Write, Edit), `Stop`, and `PreCompact` (`*`). It does not register `SessionStart`. Each command ends with `exit 0`. `inject-plan.sh` says it always exits 0 and never errors the loop. With no plan, a symlink plan, a plan outside the root, or `PLANNING_DISABLED=1`, it exits 0 and injects nothing.

`PreCompact` prints a flush reminder and a SHA line. It does not print the plan body and does not block compaction. The skill text says the protection is "the plan is on disk and will be re-read," not "the plan stays in context." That matches the Claude reference: `PreCompact` stdout is not one of the four events whose plain stdout is added to context.

`Stop` is advisory in legacy and autonomous mode. Gated mode may block, and only when mode is gated, a phase is `in_progress`, `stop_hook_active` is false, the block count is under the cap, and the ledger progressed. Their note on issue #178: an incomplete plan is normal, and blocking every stop makes users angry. They also say imperative text in a `reason` field becomes a continuation command. Host tiers in that skill: Claude can hard-block; Cursor gets a follow-up message; some hosts can only notify.

Two sessions can overwrite one `task_plan.md`. Their guard notices a drop in completed markers and prints advice. It does not lock, and the warning goes to whichever session fires next. Attestation is a read-side hash check so untrusted plan text is not injected; it does not stop a stale write.

Per-tool injection was later dropped in autonomous mode as the expensive part. Turn-start injection stayed.

`session-catchup.py` is something the skill tells the model to run. It is not a Claude `SessionStart` hook in this frontmatter. The Codex adapter is a separate `.codex/hooks.json` that does call it from `SessionStart`.

**Use:** disk file, read-only hook, exit 0 when absent or broken, no compaction block, no per-tool recitation, narrow Stop behavior, honest Cursor follow-up instead of a fake hard block.

**Do not copy:** three planning files, phase trees, ledgers, attestation, per-tool hooks, `/goal` and `/loop` wrappers, or catchup from host transcript stores.

## Boundaries

**Session start and resume.** Claude `SessionStart` `startup`, `resume`, `clear`, and `fork` can inject the one-liner if an always-on hook is installed. Skill-frontmatter hooks miss the start of a process that has not invoked the skill. Cursor `sessionStart` is documented for a new composer only. Cloud agents skip it. Reopening an existing Cursor chat is not documented as `sessionStart`.

**Compaction.** Claude: `SessionStart` matcher `compact` re-injects after auto or manual compaction, and the first response waits. Do not use `PreCompact` to store the list or to block compaction. `PostCompact` can see `compact_summary` and cannot add context. Cursor `preCompact` can show the user a message and cannot change compaction or feed the model. After Cursor compaction, the file is still on disk; getting it back into the model is the skill telling the agent to read the file, which is model discipline, not a hook.

**Response completion.** Claude `Stop` can continue the turn with `additionalContext` while items remain, `mode` is `tracking`, and `stop_hook_active` is false. That is the only documented way to pull the agent back at the end of a turn. It also continues an ordinary answer. `last_assistant_message` is available if a script wants to look at the answer; the reference does not define a "work complete" signal. Cursor `stop` can auto-submit `followup_message`, capped at 5 by default, and its input does not include the assistant text. `afterAgentResponse` has the text and no documented way to talk back. `beforeSubmitPrompt` can only allow or block the user's send.

**Pause and unrelated questions.** No hook field means "this question is off the list." A `paused` or `stopped` mode in the file is deterministic: the script prints nothing and exits 0. **Inference:** the skill sets that mode when the user pauses, stops, or changes direction, before it answers. A side question answered while mode is still `tracking` will still trip a `Stop` continuation. Skipping `UserPromptSubmit` / `beforeSubmitPrompt` avoids attaching a reminder to every send. Skipping per-tool hooks avoids a reminder on every investigation call.

**Concurrency.** Claude runs matching hooks in parallel. Cursor runs every matching source and merges. A read-only script is safe under that. Two agents writing one JSON file are not serialized by either host. Planning with Files hit the same race. **Inference:** the hook never writes. The agent writes with a temp file and rename, and refuses to create a second list while one is `tracking`. That is an application rule, not a host lock. `conversation_id` / `session_id` identify the owner. They do not isolate the file.

**State safety.** A reminder script that only reads, prints a line or empty JSON, and exits 0 cannot corrupt the file if it crashes, times out, or is missing. Claude treats a missing `Stop` script with "file not found" on stderr as non-blocking. Cursor fails open on a non-2 exit. The writer is the agent, during capture and status changes, so a dead hook leaves the last good file in place.

## Native pieces that remove custom code

- Spec progressive disclosure: the description is always visible; the procedure loads on use. No daemon, database, or server.
- Claude `SessionStart` stdout / `additionalContext`, including matcher `compact`, is the re-injection mechanism. No summary store to build.
- Claude `Stop` `additionalContext`, `stop_hook_active`, and the 8-continuation cap are the "do not conclude yet" mechanism. No loop process to build.
- Cursor `sessionStart.additional_context` and `stop.followup_message` with `loop_limit` are the same two moments, with weaker timing and a user-visible follow-up.
- Cursor's Claude-hook loader can run a project `.claude/settings.json` `Stop` hook and turn `decision: "block"` into `followup_message`. Session-start context still needs a native Cursor hook.
- `/goal` and Claude's task list do not replace the file. `/goal` is one session. `TaskCompleted` gates a task tool this research did not find documented as cross-conversation storage.

## Residual gaps

- Cursor has no documented model-context hook after compaction or on resume of an existing composer. `sessionStart` on cloud agents does not run.
- Neither host can tell "answered a side question" from "declared the tracked work done" unless the state file already says paused, or a script guesses from `last_assistant_message` (Claude only).
- Cursor `sessionStart` is fire-and-forget, so the first turn may not see `additional_context`. Claude's first response does wait.
- Skill-frontmatter hooks and skills.sh installs do not cover a new session until something invokes the skill or a settings/plugin hook is installed.
- Two concurrent writers can clobber one workspace file. The host will not stop them.

## Sources

- https://agentskills.io/specification
- https://github.com/agentskills/agentskills/blob/main/docs/specification.mdx
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/hooks
- https://code.claude.com/docs/en/hooks-guide
- https://cursor.com/docs/skills
- https://cursor.com/docs/hooks
- https://cursor.com/docs/reference/third-party-hooks
- https://cursor.com/docs/plugins/building
- https://github.com/mattpocock/skills/blob/main/.agents/invocation.md
- https://github.com/OthmanAdi/planning-with-files/blob/master/skills/planning-with-files/SKILL.md
- https://github.com/OthmanAdi/planning-with-files/blob/master/skills/planning-with-files/scripts/inject-plan.sh
