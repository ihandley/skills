# Jira

Write for a reader who opens the issue later without the author's context.

Include only sections that have content in the source:

- Problem or goal
- Current and expected behavior
- Evidence and reproduction steps
- Scope and constraints
- Acceptance criteria
- Decision, owner, and next step

Use short paragraphs for explanation and bullets for independent facts or criteria. Remove chronology unless the sequence explains the cause or the reproduction steps. The issue body states verified facts and decisions directly.

## Comments

Hedge observations, diagnoses, and recommendations. A completed result the source already states stays direct, such as "Deployment failed" or "Approved." Hedge the author's read, such as "this failed" or "X is the problem."

## Platform features

A Jira issue key stays bare, e.g. `PROJ-123`.

Link syntax when [../links.md](../links.md) says to link an external artifact: `[name](url)`.

Keep `@name` only when the source already contains that mention.

Source: `See the implementation in the web-ui repo: https://github.com/example/web-ui.`

Output: `See the implementation in the [web-ui](https://github.com/example/web-ui) repo.`

Source: `See the implementation in https://github.com/example/web-ui.`

Output: `See the implementation in https://github.com/example/web-ui.`
