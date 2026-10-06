# Pull request comments

A comment includes the relevant combination of:

- The problem or question
- Why it matters
- The requested change or decision

Do not force every comment into all three parts. "Needs a test" is sufficient when the missing case is obvious. Otherwise name the behavior that needs coverage.

Hedge observations, diagnoses, and recommendations. A completed result the source already states stays direct, such as "Deployment failed" or "Approved." Hedge the author's read, such as "this failed" or "X is the problem." Delete praise, including "Solid fix", "Nice work", "Correct fix for a real defect", and "useful complement". Do not move praise into another paragraph or replace it with approval.

Use as few sentences as those parts need. Most findings take 1-3. These rules apply to the review summary body too. Do not:

- Restate the diff. The author is looking at it.
- Explain why the submitted change is correct.
- Narrate the comment: why it is flagged, another reviewer's coverage ("Not re-raising: ...", "already covered, not restating here"), or "just making this trackable". If a prior finding needs no further comment, say nothing.
- Narrate the review process: "Re-checked fresh", "prior review auto-dismissed", "confirmed the failing check is...", "follows best-practices", or a bare "Clean." A CI result with no author action stays out of the PR.
- Phrase approval as praise. Leave an approve-only body empty. Use `Approved.` only when the decision must be explicit.

## Platform features

When [../links.md](../links.md) says to link, use `[name](url)`.

Keep `#123` or `owner/repo#123` when the source already uses that identifier. Do not invent a GitHub number from a Jira key.
