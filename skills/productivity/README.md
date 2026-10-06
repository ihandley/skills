# Productivity

General workflow tools, outside code work.

Promoted. Each skill here is listed in the top-level README, registered in `.claude-plugin/plugin.json`, and has a docs page at `docs/productivity/<skill-name>.md`.

## User-invoked

Reachable only when you type them (`disable-model-invocation: true`, and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`).

None yet.

## Model-invoked

Reachable by you or by the agent when the task fits.

- **[terse](./terse/SKILL.md)**: Rewrite or draft Slack, email, Jira, Confluence, and pull-request text to minimize length and maximize signal.
