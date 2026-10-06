# Skills

Agent skills I use. Small, composable, and installable as a Claude Code plugin or as editable files through [skills.sh](https://skills.sh).

The layout follows the bucketed plugin pattern: promoted skills live in `skills/engineering/` and `skills/productivity/`, and the Claude Code plugin ships exactly that set.

## Installation

Two ways in. The Claude Code plugin installs the promoted set as a managed bundle. skills.sh copies editable skill files into a project, for Claude Code, Cursor, Codex, and other agents. Pick one. Installing both leaves every skill twice.

Install commands are defined in [.agents/install-block.md](./.agents/install-block.md).

### Claude Code

```bash
claude plugin marketplace add ihandley/skills
claude plugin install ihandley-skills@ihandley
```

Or, from inside a session:

```
/plugin marketplace add ihandley/skills
/plugin install ihandley-skills@ihandley
```

### Cursor, Codex, and other agents

```bash
npx skills@latest add ihandley/skills
```

Pick the skills you want, and which coding agents to install them on.

To update an editable install later:

```bash
npx skills update
```

## Reference

These split on one axis: who can invoke them. **User-invoked** skills are reachable only when you type them. **Model-invoked** skills can be invoked by you or reached for by the agent when the task fits. A user-invoked skill may invoke model-invoked skills, and it never invokes another user-invoked skill.

### Engineering

Skills for daily code work.

**User-invoked**

None yet.

**Model-invoked**

- **[init-ai](./skills/engineering/init-ai/SKILL.md)**: Write or update a minimal `AGENTS.md` from verified commands, conventions, and gotchas, plus a `CLAUDE.md` stub. Shows the draft and asks before writing.

### Productivity

General workflow tools, outside code work.

**User-invoked**

None yet.

**Model-invoked**

None yet.
