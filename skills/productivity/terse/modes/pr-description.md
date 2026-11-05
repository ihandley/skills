# Pull request description

- When another active skill requires a PR body structure or visual, preserve it. Apply every content rule in `SKILL.md` and in the Rules section below within that structure. Do not apply the Structure section, and do not drop a required section or visual to shorten the body.
- When rewriting an existing draft, treat its sections and visuals as required when they match a known PR template.

## Structure

- Keep the prose under 15 lines. The Summary visual is exempt.
- The Summary visual is required when a shape, flow, or boundary is the point. Use the smallest one: pseudocode, a call tree, a component tree, a file tree, mermaid, or a diff. Add a second visual only when it shows a different boundary.
- Include Evidence only when the diff or the source shows both a before and an after. Do not invent either side.
- Include a Merge Danger line only when the diff or the source supports it. Do not invent a door or a blast radius.

```markdown
## Summary

[1-2 sentences: why, and context the diff does not show]

[smallest visual]

**Ticket:** PROJ-123

## Evidence

- **Before:** [failing output or screenshot]
  **After:** [passing output or screenshot]

## Merge Danger

**Door:** [one-way or two-way]

**Blast Radius:** [one word]
```

- A two-way door can be rolled back. A one-way door cannot.
- Blast Radius is one word for the scope, such as `callers` or `layout`.
- Add one sentence under Merge Danger only when the source states a ramification of the merge.
- Include the ticket line only when the source names a ticket. If the source contains the ticket URL, link the key as `[PROJ-123](url)`. Do not invent the URL.

## Rules

- Do not list every modified file, and do not walk an edit the visual already shows.
- Do not restate the commit log.
- Omit an empty section. Do not write `## Questions`, `## TO-DOs`, or `N/A`.
- Do not copy QA steps or the ticket spec into the body.
- Wrap benchmark output, large payloads, or logs in `<details><summary>...</summary></details>`.

## Platform features

Ticket and issue links follow [../links.md](../links.md). Keep `#123` or `owner/repo#123` when the source already uses that identifier.
