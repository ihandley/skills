## What it does

`init-ai` writes one short `AGENTS.md` for a repository, plus a `CLAUDE.md` stub that points at it. The file holds commands, conventions, and gotchas that would cause a mistake if the agent did not have them.

The constraint is verification. Commands are copied from a manifest, CI config, or something a person already stated. The skill does not invent a build command, and it does not write an architecture tour. Anything it cannot verify is left as `TODO(human)` instead of a guess. A checker then fails the result if the root file passes 100 lines, or a child file passes 60.

## When to reach for it

Type `/init-ai`, or the agent reaches for it when you ask to generate, create, or update `AGENTS.md`, or to document a codebase for agents.

Reach for it on a repo that has no agent instructions, or on one whose `AGENTS.md` has drifted into a restatement of the README. It is the wrong tool when you want a design discussion, a code review, or a long onboarding guide.

## Common questions

**Will it overwrite an `AGENTS.md` I already edited?**
It edits in place, and it asks first when your existing file is aiming at something other than this skill's output. It shows the detected facts, the proposed text, and a one-phrase cost for each paragraph before it writes.

**What if `CLAUDE.md` already has real content?**
It leaves that file alone and reports the path. It only writes `CLAUDE.md` when the file is missing, or when it is already the `@AGENTS.md` stub.

**Does it create an `AGENTS.md` in every package?**
No. A child file is proposed only when a subdirectory has local instructions that do not belong at the root, and only after you agree.

**What is the codesearch step?**
If a `codesearch` MCP server is already configured, the skill asks once whether to use it to verify organization-specific names. With no server configured, it skips that step. It does not try to install one.

## It's working if

- You confirmed the draft before any file was written.
- Root `AGENTS.md` is under 100 lines, and any child file is under 60.
- `CLAUDE.md` next to each new `AGENTS.md` is exactly `@AGENTS.md`, unless an existing `CLAUDE.md` was left untouched on purpose.
- `scripts/check-agents-md.sh` reports no `FAIL`. Any `WARN` is in the final report.
- Unverified conventions are `TODO(human)` markers, not guessed prose.
