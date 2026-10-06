## What it does

`deslop` strips AI-authoring artifacts from the changes on your branch: comments that restate the code, narrated line comments, ticket IDs left as provenance, `try/catch` and null checks that guard nothing, and type escapes where a precise type exists. It diffs against the PR base, or `origin/HEAD` when there is no PR.

The constraint is that behavior must not change. It edits only lines the branch changed, leaves any code edit alone when behavior might change, and never touches pre-existing lint pragmas, license headers, or public-API doc comments. It runs the narrowest existing compile or test on what it touched, and it does not commit.

## When to reach for it

Type `/deslop`, or the agent reaches for it when you say "deslop", "remove AI slop", or "clean up this code before commit".

Reach for it after an agent has written code and before you commit or open a PR. It is the wrong tool for refactors that change reuse, efficiency, or structure, and for Slack, email, or PR prose.

## Common questions

**Does it touch code outside my changes?**
No. It edits added and changed hunks only, and leaves the rest of each file alone.

**Will it delete a ticket number I want to keep?**
It removes IDs left as provenance and writes the reason in words, since git blame already links the change. It keeps an ID only when the code depends on its value.

**Will it remove a `try/catch` that handles a real failure?**
No. It keeps a catch that translates a known failure or restores an invariant. It cuts one that only logs, swallows, or wraps a call that cannot throw on that path. When it cannot tell, it leaves the code.

## It's working if

- The diff shrinks without any behavior change, and the compile or test it ran passes.
- Linter pragmas, license headers, and public-API doc comments are intact.
- Nothing was committed.
- The report is one to three sentences.
