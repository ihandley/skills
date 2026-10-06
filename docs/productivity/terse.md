## What it does

`terse` rewrites or drafts workplace text for Slack, email, Jira, Confluence, and pull requests so it is as short as it can be without losing meaning. It leads with the point, cuts rationale the reader does not need, and scrubs the tells that make text read as machine-written.

The constraint is that it keeps your facts, certainty, and the force of any request. It never uses an em dash or en dash, and it checks that with a bundled script before it returns text. Each medium has its own rules under `modes/`, and a voice file controls tone.

## When to reach for it

Type `/terse`, or the agent reaches for it when you ask to rewrite pasted text or draft one of those media.

Reach for it on any text another person will read. It is the wrong tool for code, commit diffs, or long-form documents where length is the point. For code cleanup, use `deslop`.

## Common questions

**Which medium does it use?**
It picks the matching mode, such as `slack` or `pr-description`, and falls back to `default`. It asks only when plausible media need different structure or platform syntax.

**How do I set my own voice?**
Copy `voice.md` from the skill to `~/.claude/terse-voice.md`. The skill loads that file first, then a repo-level `.claude/terse-voice.md`, then the shipped default. An update overwrites the installed `voice.md`, not your personal file.

**What does it need installed?**
Python 3, for the dash check.

## It's working if

- The point or decision is in the first sentence.
- No em dash or en dash appears, and `scripts/check-dashes` exits 0.
- Facts, uncertainty, and requests match the source.
- No praise remains.
