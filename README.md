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

- **[understand](./skills/engineering/understand/SKILL.md)**: Understand a subject one portion at a time, in arrival order, and stay there until you release the turn. Writes only a learning journal.
- **[pair](./skills/engineering/pair/SKILL.md)**: Teach-as-you-go pairing. You write the code; the agent explains the design, plans the steps, and checks understanding before editing anything.

**Model-invoked**

- **[deslop](./skills/engineering/deslop/SKILL.md)**: Scrub AI-generated comments, over-defensive checks, and type escapes from a branch diff before commit or PR.
- **[agents-md](./skills/engineering/agents-md/SKILL.md)**: Write or update a minimal `AGENTS.md` from verified commands, conventions, and gotchas. Shows the draft and asks before writing.
- **[skill-compress](./skills/engineering/skill-compress/SKILL.md)**: Compress a `SKILL.md` and its support files for execution density without losing behavior.
- **[pr-review](./skills/engineering/pr-review/SKILL.md)**: Review a pull request by fetching and following the LiveViewTech pr-review skill.

### Productivity

General workflow tools, outside code work.

**User-invoked**

None yet.

**Model-invoked**

- **[terse](./skills/productivity/terse/SKILL.md)**: Rewrite or draft Slack, email, Jira, Confluence, and pull-request text to minimize length and maximize signal.
- **[stepper](./skills/productivity/stepper/SKILL.md)**: Stick to one ordered list of work, and brief before any new start.
- **[ticketer](./skills/productivity/ticketer/SKILL.md)**: Create or update Jira and GitHub Issues tickets with team rules enforced by a CLI and a confirmation gate before anything is filed.
- **[tidy](./skills/productivity/tidy/SKILL.md)**: Reconcile local branches with pull requests and the tracker in `~/.claude/tidy.yaml`, then delete branches the pull request already took.
- **[alias](./skills/productivity/alias/SKILL.md)**: Cache names, ids, and pronouns, and skip a lookup when the id is already stored.

## Releasing

PR titles must be Conventional Commits (`feat:`, `fix:`, `chore:`, `feat!:` for breaking). Squash merges make the title the commit, and release-please reads those commits to open a release PR. Merging that PR bumps `.claude-plugin/plugin.json` and tags the release, and `/plugin` then picks up the update.
