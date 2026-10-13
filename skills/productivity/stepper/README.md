# Stepper

Stepper tracks a short list of outstanding commitments for the current Cursor or Claude Code session. The `stepper.py` CLI is the only way to change that state.

## Install the skill

From this repository, with the other promoted skills:

```bash
claude plugin marketplace add ihandley/skills
claude plugin install ihandley-skills@ihandley
```

Or, for Cursor and other agents:

```bash
npx skills@latest add ihandley/skills
```

Pick Stepper. Installing the skill does not register hooks.

## Install hooks

Hooks are optional, per platform, and reversible. From the skill directory:

```bash
python3 stepper.py hooks install cursor
python3 stepper.py hooks install claude
python3 stepper.py hooks status
python3 stepper.py hooks uninstall cursor
python3 stepper.py hooks uninstall claude
```

`install` with no platform changes nothing. Cursor writes `~/.cursor/hooks.json`. Claude Code writes `~/.claude/settings.json`. Uninstall removes only commands tagged `--tag stepper` for that platform. A settings file that is not valid JSON is left untouched. Set `STEPPER_HOME` to redirect those paths.

Each platform's hook exits when it sees the other platform's event names. Installing Claude hooks does not also drive Cursor when Cursor imports Claude settings.

Without hooks, explicit commands still work. Proactive offers, session reminders, and compaction reinjection do not.

## Use

Ask the agent to track the outstanding items, or accept when it offers. Examples:

- "Track these two acceptance criteria."
- "What's left?"
- "Mark that complete."
- "Pause Stepper."

The agent passes a session key supplied by a hook. One session holds one context. A second conversation does not attach unless you ask it to take over that work.

State lives in `.stepper/` in the repository you are working in. The first write adds `.stepper/` to that clone's `.git/info/exclude`. Installing or updating the skill does not touch this directory.

## Limitations

- A non-empty evidence string is stored as written. The CLI does not check that it is true.
- A corrupt context file is left in place. Stepper does not repair it or create a replacement with the same id.
- A crashed session keeps its lease until you explicitly take it from another session.
- Hooks cannot ask a yes/no question. The agent asks.
- Cursor `agent --print` 2026.10.01, in a trusted workspace with a logging hook, fired `sessionStart`, then `preToolUse`, then `postToolUse`. It did not fire `afterAgentResponse` or `stop`. Same-turn offer injection is implemented only when `afterAgentResponse` has already stored a candidate and a later `postToolUse` in that same generation runs. That order was not observed. In this IDE session, `postToolUse` ran as tools finished and `afterAgentResponse` did not run between those calls. A list that appears only in the final message therefore depends on `stop`, which the CLI run did not exercise. Fixture tests cover that payload. They are not a live platform test.
- Cursor user hooks do not run in cloud agents. `sessionStart` does not cover compaction. Compaction reinjection waits for the next tool result, or for `stop` if no tool follows.
- Claude Code has no `afterAgentResponse`. A proactive offer there is a `Stop` continuation. Live Claude hook execution was not run.
- Keyword classification can miss an unusual request or send one extra follow-up.
