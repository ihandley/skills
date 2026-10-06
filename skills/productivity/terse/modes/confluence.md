# Confluence

- Start with the document's purpose or decision.
- State verified facts and decisions directly. Do not hedge them.
- Record decisions, rationale, constraints, owners, and consequences that are in the source.
- Include implementation details only when the source needs them for someone to operate or change the system.
- Do not repeat the introduction in a closing summary.
- Keep a cause and its consequence in the same paragraph.
- When pasted material only restates a linked ticket or page, replace that material with the link. Keep pasted evidence, reproduction steps, decisions, and context this document adds.

## Platform features

Link syntax when [../links.md](../links.md) says to link: `[name](url)`.

Keep a Confluence mention only when the source already contains it. A Jira issue key stays bare unless the source also contains its URL.

Source: `Tracked in PROJ-123.`

Output: `Tracked in PROJ-123.`

Source: `Tracked in PROJ-123: https://example.atlassian.net/browse/PROJ-123.`

Output: `Tracked in [PROJ-123](https://example.atlassian.net/browse/PROJ-123).`

Source: `The implementation is in https://github.com/example/web-ui.`

Output: `The implementation is in https://github.com/example/web-ui.`
