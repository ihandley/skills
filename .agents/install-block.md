# The canonical install block

One install story, one wording. `README.md` and every page under `docs/` say this and nothing else. Change it here first, then propagate.

This repo is its own Claude Code marketplace. It is not in Claude Code's official marketplace, so the marketplace add step stays in the documented install.

## Claude Code: the plugin

<canonical-block name="claude-code">

```bash
claude plugin marketplace add ihandley/skills
claude plugin install ihandley-skills@ihandley
```

Or, from inside a session:

```
/plugin marketplace add ihandley/skills
/plugin install ihandley-skills@ihandley
```

</canonical-block>

## Cursor, Codex, and other agents: skills.sh

The plugin is Claude Code only. Everywhere else, skills.sh copies editable skill files into the project.

<canonical-block name="skills-sh-whole-set">

```bash
npx skills@latest add ihandley/skills
```

Pick the skills you want, and which coding agents to install them on.

</canonical-block>

Single-skill form, wherever one skill is named on its own:

<canonical-block name="skills-sh-one-skill">

```bash
npx skills@latest add ihandley/skills --skill=<name>
```

```bash
npx skills@latest update <name>
```

</canonical-block>

## The two routes are exclusive

The plugin is a managed bundle. skills.sh writes files you own and edit. Installing both leaves every skill twice. Always say "pick one".
