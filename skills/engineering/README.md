# Engineering

Skills for daily code work.

Promoted. Each skill here is listed in the top-level README, registered in `.claude-plugin/plugin.json`, and has a docs page at `docs/engineering/<skill-name>.md`.

## User-invoked

Reachable only when you type them (`disable-model-invocation: true`, and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`).

None yet.

## Model-invoked

Reachable by you or by the agent when the task fits.

- **[init-ai](./init-ai/SKILL.md)**: Write or update a minimal `AGENTS.md` from verified commands, conventions, and gotchas, plus a `CLAUDE.md` stub. Shows the draft and asks before writing.
