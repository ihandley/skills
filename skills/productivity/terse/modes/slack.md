# Slack

- Hedge observations, diagnoses, and recommendations. A completed result the source already states stays direct, such as "Deployment failed" or "Approved." Hedge the author's read, such as "this failed" or "X is the problem."
- Put the update in the first sentence.
- One idea per message. If one paste contains multiple ideas, separate them with a blank line.
- Use short paragraphs for context that belongs to one idea.
- Use fragments and contractions.
- A routine message is 1-3 sentences. Use more when the reader needs that context to understand the issue or take action.

## Dense technical questions

When the source contains more than one of these, keep them in separate paragraphs: requirement, implementation conflict, documentation gap, decision request.

- Do not collapse that message into one paragraph to reduce its length.
- Preserve the writer's technical vocabulary.

## Platform features

Link syntax when [../links.md](../links.md) says to link: `<url|label>`.

Keep `<@U...>`, `<#C...>`, or `<!subteam^...>` only when the source already contains that token. A bare name stays text.

Source: `Can you look at PROJ-123?`

Output: `Can you look at PROJ-123?`

Source: `The implementation is in the web-ui repo: https://github.com/example/web-ui.`

Output: `The implementation is in the <https://github.com/example/web-ui|web-ui> repo.`

Source: `The implementation is in https://github.com/example/web-ui.`

Output: `The implementation is in https://github.com/example/web-ui.`
