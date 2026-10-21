# Model-invoked vs user-invoked

Every `SKILL.md` in this repo is a skill. The axis that splits them is who can reach it:

- **User-invoked**: reachable only when the human types its name. Set `disable-model-invocation: true` in the frontmatter, and `policy.allow_implicit_invocation: false` in `agents/openai.yaml`. The `description` is human-facing: a one-line summary for someone browsing slash-commands.
- **Model-invoked**: reachable by the model or the user. Omit `disable-model-invocation` and the `policy` block. The `description` is model-facing and keeps trigger phrasing ("Use when the user wants…, mentions…, asks for…") so auto-invocation can fire. Keep a skill model-invoked when the model could usefully reach for it on its own.

Each harness excludes a user-invoked skill from the model's reach in its own way. A user-invoked skill may invoke model-invoked skills. It never invokes another user-invoked skill.

Every skill also carries an `agents/openai.yaml` beside its `SKILL.md`. It holds Codex UI metadata (`interface.display_name`, `interface.short_description`) and, for user-invoked skills, the `policy.allow_implicit_invocation: false` that pairs with `disable-model-invocation`. A skill is user-invoked in both harnesses, or in neither.

Bucket `README.md`s and the top-level `README.md` group entries into **User-invoked** and **Model-invoked**.

## Dependencies between them

Dependencies are an explicit instruction to call the Skill tool with the named skill (`Call the Skill tool with "grilling"`). A step that needs two skills is two calls. This only works when the named skill is model-invoked. When a step depends on a user-invoked skill, tell the human to run it.

## Who owns the turn

One skill owns the turn. The harness still routes. A latch file, `.claude/turn-owner.json` in the workspace, records the owner for one session. Hooks honor it only when `session_key` matches. The key is `claude:<session_id>` or `cursor:<conversation_id>`, the same key stepper uses.

- Stepper owns the list. While the owner is understand or pair, stepper leaves the list leased and does not inject its reminder.
- Terse owns the outward draft: Slack, email, Jira, Confluence, or a pull request. It stops when that draft is delivered.
- Ticketer owns the ticket payload.
- Understand owns the voice, the topic, and what may be written while it owns the turn. The learning journal is the only write.
- Pair owns the turn the same way while that is the session the human started. The understand offer stays quiet.
