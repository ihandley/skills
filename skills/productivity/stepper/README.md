# Stepper

**Lightweight working memory for AI coding agents.** Stepper keeps track of outstanding acceptance criteria, review findings, and other concrete commitments so Cursor or Claude Code can return to them after a long investigation.

Stepper is **not** a project planner. It tracks a small list of work within an agent session, keeps one item active, and reminds the agent what remains. A deterministic Python CLI owns the state; the agent interprets requests, performs the work, and supplies verification evidence.

> **Implementation status:** Stepper is currently being developed on the [`feature/stepper`](https://github.com/ihandley/skills/tree/feature/stepper) branch. Proactive detection and some hook lifecycles have not yet been verified end-to-end in both agents. See [Current limitations](#current-limitations).

## What it looks like

**Automatic suggestion (when hooks are working):**

1. Ask your agent to review an implementation against acceptance criteria.
2. The agent reports that AC-3 and AC-4 remain outstanding.
3. Stepper detects the actionable list and the agent asks whether you'd like to track it.
4. Say **yes**. Stepper captures the list and focuses AC-3.
5. The agent works on AC-3, records evidence when it's verified, and is reminded that AC-4 is next.

Stepper **never starts tracking a detected list without your confirmation**. If you decline, it won't repeatedly offer the same list.

**Explicit tracking:**

> Use Stepper to track the remaining acceptance criteria while you implement them.

Explicit tracking is a good starting point while proactive hook integration is being validated.

Sub-steps stay under the acceptance criterion they belong to. Ask to track them as sub-steps of that item. Stepper keeps two levels of children, preserves ids such as `AC-3b-1`, and does not mark the parent verified when the children are finished.

## Requirements

- Python 3 (standard library only; no pip dependencies)
- Cursor and/or Claude Code
- A local checkout of the repository you're working in
- Stepper installed as an agent skill
- Optional: Stepper hooks for automatic suggestions, reminders, and compaction recovery

## Install

### 1. Install the skill

**Claude Code — marketplace installation:**

```bash
claude plugin marketplace add ihandley/skills
claude plugin install ihandley-skills@ihandley
```

**Cursor — skills installer:**

```bash
npx skills@latest add ihandley/skills
```

Select **Stepper** when prompted.

**While Stepper lives only on `feature/stepper`:** the commands above may install from the repository's default branch, which might not contain Stepper yet. For development, check out the feature branch and use the skill files from `skills/productivity/stepper/` in that checkout. Verify that your agent can see the `stepper` skill before proceeding.

### 2. Enable hooks (recommended)

Installing an Agent Skill **does not automatically install Stepper's hooks**. Hooks enable proactive offers, session reminders, and compaction recovery.

From the directory containing the installed `stepper.py`:

```bash
# Enable one or both platforms
python3 stepper.py hooks install cursor
python3 stepper.py hooks install claude

# Inspect installation
python3 stepper.py hooks status
```

The installer modifies only the selected platform's user settings:

| Platform | Hook settings file |
| --- | --- |
| Cursor | `~/.cursor/hooks.json` |
| Claude Code | `~/.claude/settings.json` |

Installation preserves unrelated hook entries and creates a backup before modifying an existing settings file. Hooks use the absolute path to the `stepper.py` script, so **keep the installed skill directory in place** after enabling them. Restart or start a fresh agent session as needed for settings changes to take effect.

To remove the hooks without deleting the skill or tracked state:

```bash
python3 stepper.py hooks uninstall cursor
python3 stepper.py hooks uninstall claude
```

Hooks are optional and installed independently for each platform. Without hooks, the CLI still works, but the automatic behavior does not.

## Usage

You interact with Stepper by talking to your coding agent. The agent invokes the CLI on your behalf.

| Say this | Expected behavior |
| --- | --- |
| “Track these acceptance criteria with Stepper.” | Create a tracked context |
| “What's left?” | Brief: done, left, blocked, and where the active item sits |
| “/stepper status” | Each item on its own row |
| “Focus on AC-4.” | Make AC-4 the active item when its dependencies are met |
| “Mark AC-3 complete; the integration test passes.” | Record verification evidence |
| “We're blocked on AC-5 until the API is available.” | Hold on AC-5 and recommend waiting |
| “Skip to the next item.” | Move on only when that item does not depend on the held one |
| “Defer AC-4.” | Postpone that item without marking it done |
| “Pause Stepper.” | Suppress reminders temporarily |
| “Resume Stepper.” | Restore reminders |
| “Stop tracking this.” | Close the context without falsely verifying unfinished work |

### A typical workflow

```text
You:    Review these four acceptance criteria. Two appear unfinished.
Agent:  AC-1 and AC-2 are satisfied. AC-3 and AC-4 remain.
Agent:  Would you like me to track AC-3 and AC-4 with Stepper?
You:    Yes.
Agent:  Tracking AC-3 (active) and AC-4 (pending).

        ... lengthy investigation and implementation of AC-3 ...

Agent:  AC-3 verified: integration test passes.
Stepper: AC-4 is still pending.
Agent:  Moving on to AC-4.
```

Verification requires a nonempty evidence note. The CLI checks that the note exists; **the agent is responsible for determining whether the evidence actually proves the criterion**.

### Item states

- **Pending:** actionable work not yet active
- **Active:** the one item currently being addressed
- **Blocked:** waiting for a dependency
- **Verified:** recorded complete with evidence
- **Deferred:** intentionally postponed, not complete
- **Cancelled:** explicitly removed from scope, not verified

Blocked and deferred work remains outstanding. Closing tracking does not mark unfinished items complete.

## Sessions and persistence

Stepper stores state under `~/.stepper` in the home directory, separate from the installed skill and from the checkout. Nothing is written into the project's git exclude or `.gitignore`.

- Each tracked context has its own JSON file.
- Each Cursor conversation or Claude Code session has a separate session binding.
- A context is leased to one session at a time, preventing two conversations from silently changing the same tracked list.
- A new capture never overwrites another session's open list. Capture names the context. An open name is refused, and the lease stays where it is.
- The same supported session can recover its state after resume or compaction.
- A **new** conversation does not automatically take over an existing context. Ask it to continue that tracked work explicitly; takeover requires your authorization.
- A crashed session may retain its lease until you explicitly transfer it.

Hooks pass the session identifier and the checkout to the agent. The agent copies both from the `Stepper session:` line and does not construct a key from a transcript path. A command that changes a list also passes that list's name as `--context`. **Do not manually edit files in `~/.stepper`.**

## CLI reference

Most users should not need to run these commands directly. For troubleshooting or agent integration, pass `--root` with the project the hook named. The skill directory is not that project. State-changing commands require a valid hook-registered session key.

```bash
python3 stepper.py status --root /path/to/project
python3 stepper.py status --session 'cursor:<conversation-id>' --root /path/to/project
python3 stepper.py capture --session 'cursor:<conversation-id>' --root /path/to/project \
  --context auth-fix \
  --item 'AC-3: reset email is sent' \
  --item 'AC-4: expired tokens are rejected'
python3 stepper.py focus --session 'cursor:<conversation-id>' --root /path/to/project --context auth-fix AC-4
python3 stepper.py verify --session 'cursor:<conversation-id>' --root /path/to/project --context auth-fix AC-3 \
  --evidence 'Integration test passed'
python3 stepper.py pause --session 'cursor:<conversation-id>' --root /path/to/project --context auth-fix
python3 stepper.py resume --session 'cursor:<conversation-id>' --root /path/to/project --context auth-fix
python3 stepper.py close --session 'cursor:<conversation-id>' --root /path/to/project --context auth-fix
```

The agent should supply the session key and project root from the hook line, not the placeholders above. Other commands include `add`, `block`, `unblock`, `defer`, `cancel`, `attach`, `detach`, and `decline`.

## Current limitations

- **Proactive candidate detection on Claude Code is fixture-tested.** An ordinary prompt creates no session file. `Stop` creates one only when `last_assistant_message` contains a new candidate, and a repeated `Stop` does not offer it again. A live Claude Code 2.1.287 session did confirm that an explicit tracking prompt receives `Stepper session: claude:<session_id>` from `UserPromptSubmit`, and `--resume` still has that key. An unrelated prompt does not receive it.
- **Cursor hook execution is only partly live-tested.** `agent --print` 2026.10.01 fired `sessionStart`, `preToolUse`, and `postToolUse`. It did not fire `afterAgentResponse` or `stop`. An IDE logging hook later showed a finished turn as the last `postToolUse`, then `afterAgentResponse`, then `stop` with a new generation id and no response text. The offer uses the stored response and does not wait for another tool call in that generation. Stepper's handling of those payloads is fixture-tested. The logging hook did not run Stepper.
- A candidate detected only in a final assistant response may require **one additional agent turn** to ask for confirmation.
- Hooks cannot ask you a question directly; they prompt the agent to ask.
- Candidate detection intentionally favors conservative patterns and may miss unusual wording.
- User-level Cursor hooks do not run in Cursor cloud agents.
- Session recovery and compaction behavior differ between Cursor and Claude Code; not every path has been tested in a live session.

For now, start with **explicit tracking** in a real coding task and confirm that Stepper returns to the next outstanding item after finishing the current one.

## Source

- [Stepper skill directory](https://github.com/ihandley/skills/tree/feature/stepper/skills/productivity/stepper)
- [Architecture proposal](https://github.com/ihandley/skills/blob/feature/stepper/skills/productivity/stepper/proposal.md)
