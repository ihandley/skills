# Engineering

Skills for daily code work.

Promoted. Each skill here is listed in the top-level README, registered in `.claude-plugin/plugin.json`, and has a docs page at `docs/engineering/<skill-name>.md`.

## User-invoked

Reachable only when you type them (`disable-model-invocation: true`, and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`).

- **[chad-learn](./chad-learn/SKILL.md)**: Reconstruct existing code in the order it could have been built, one decision at a time. Writes only a learning journal.
- **[pair](./pair/SKILL.md)**: Teach-as-you-go pairing. You write the code; the agent explains the design, plans the steps, and checks understanding before editing anything.

## Model-invoked

Reachable by you or by the agent when the task fits.

- **[deslop](./deslop/SKILL.md)**: Scrub AI-generated comments, over-defensive checks, and type escapes from a branch diff before commit or PR.
- **[agents-md](./agents-md/SKILL.md)**: Write or update a minimal `AGENTS.md` from verified commands, conventions, and gotchas. Shows the draft and asks before writing.
- **[skill-compress](./skill-compress/SKILL.md)**: Compress a `SKILL.md` and its support files for execution density without losing behavior.
- **[pr-review](./pr-review/SKILL.md)**: Review a pull request by fetching and following the LiveViewTech pr-review skill.
