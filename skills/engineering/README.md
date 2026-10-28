# Engineering

Skills for daily code work.

Promoted. Each skill here is listed in the top-level README, registered in `.claude-plugin/plugin.json`, and has a docs page at `docs/engineering/<skill-name>.md`.

## User-invoked

Reachable only when you type them (`disable-model-invocation: true`, and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`).

- **[understand](./understand/SKILL.md)**: Understand a subject one portion at a time, in arrival order, and stay there until you release the turn. Writes only a learning journal.
- **[pair](./pair/SKILL.md)**: Teach-as-you-go pairing. You write the code; the agent explains the design, plans the steps, and checks understanding before editing anything.
- **[pr-queue](./pr-queue/SKILL.md)**: List the open sprint's In Review tickets and the last 7 days of pull requests, and track that list until you start qpre.
- **[dependabot-review](./dependabot-review/SKILL.md)**: Review one dependency-bump pull request and file the ticket.
- **[friction](./friction/SKILL.md)**: Review one pasted workflow, separate friction from controls, and return a teardown, a blueprint, and a roadmap.

## Model-invoked

Reachable by you or by the agent when the task fits.

- **[deslop](./deslop/SKILL.md)**: Scrub AI-generated comments, over-defensive checks, and type escapes from a branch diff before commit or PR.
- **[agents-md](./agents-md/SKILL.md)**: Write or update a minimal `AGENTS.md` from verified commands, conventions, and gotchas. Shows the draft and asks before writing.
- **[skill-compress](./skill-compress/SKILL.md)**: Compress a `SKILL.md` and its support files for execution density without losing behavior.
- **[pr-review](./pr-review/SKILL.md)**: Review a pull request by fetching and following the LiveViewTech pr-review skill.
