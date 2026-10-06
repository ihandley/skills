---
name: deslop
description: Strip AI-written residue from the code changed on this branch before commit or PR, without changing behavior. Use when the user says "deslop", "remove the AI slop", "clean this up before I commit", or code looks over-commented or over-defended. Not for refactors. Not for Slack, email, or PR prose.
---

Remove what an agent added that a careful human would not have. Touch only lines this branch changed. Behavior stays identical. Never commit.

## §1 Scope

1. Base: the open PR's base branch if one exists (`gh pr view --json baseRefName`), else the default branch.
2. Diff: `git diff $(git merge-base HEAD <base>)`, which covers committed and uncommitted work.
3. Edit added or changed lines only. Leave the rest of each file as it is.

## §2 Cut

- **Restating comments.** A comment that says what the next line already says. Keep one only for a reason the code cannot show: a workaround, an outside-API quirk, an invariant. A better name beats a comment.
- **Narration.** Multi-line comments walking through the code. Shrink to one line above the block, or delete.
- **Authoring-process notes.** "Added for review", "now handles X", "Bugbot flagged", confidence labels, "as of <date I looked>". Keep the underlying reason as plain prose, or delete.
- **Provenance IDs.** Ticket, issue, PR, or RFC IDs and URLs in comments, test names, and doc headings. Git blame already links the change. Write the reason in words. Keep an ID only when the code depends on its value.
- **Defense with nothing to defend against.**
  - A `catch` that only logs, swallows, or rethrows the same error.
  - A null or bounds check the types or an earlier line already guarantee.
  - Validating arguments from a trusted internal caller.
  - Keep a check at a real boundary: I/O, user input, an external payload, or a callee documented to throw.
- **Type escapes.** `any`, blanket casts, and new suppression annotations where a real type can be named. Keep at a genuinely untyped edge, scoped to it.
- **Docstrings that echo the signature** on small private helpers.
- **Style drift.** Bring changed lines in line with the file's comment style, naming, and idiom. Do not restyle lines this branch did not change.

## §3 Leave alone

- Lint, type-check, and formatter pragmas that existed before this branch.
- License headers.
- Public-API doc comments, even long ones.
- A comment that is itself the reason for the code.
- Any code edit where behavior might change. Leave it and say so in the report.

## §4 Verify

Run the narrowest existing compile or test that covers the touched files. If it fails, revert the edit that caused it.

## §5 Report

One to three sentences: what was removed, and anything left because the behavior was unclear.
