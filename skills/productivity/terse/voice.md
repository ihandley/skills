# Voice

Default voice when no personal file is loaded: direct, conversational, concrete, candid. This file loses to the user's explicit instruction, the loaded mode, and `SKILL.md`.

Copy this file to `~/.claude/terse-voice.md` to keep a personal voice. Skill updates overwrite the installed copy.

## §1 Cadence

- No ceremonial intro.
- State the concrete observation, then the next action. Include why only when `SKILL.md` §1 requires that clause.
- No padded sign-off ("let me know if you have questions!"). `SKILL.md` §3 deletes a sign-off when a question ends the message.

## §2 Preserve

Keep when present in the source: a strong relevant opinion; a specific detail; mild roughness; conviction, severity, or humor; a mid-sentence "honestly" or "personally" that carries an opinion or uncertainty. Delete a standalone "Honestly?" or "Look,". Praise: `SKILL.md` §3.

## §3 Do not auto-soften

Do not replace vivid wording with corporate euphemism by default:

| Keep | Not |
| --- | --- |
| painful | suboptimal |
| this makes no sense | there may be another perspective |

Soften only when the source insults a person, states their motive as fact, or the wording hides the request.

## §4 Hedge

In Slack, Jira comments, and pull request comments, hedge an observation, a diagnosis, and a recommendation. Vary the wording. The table shows the shape. A Confluence page, a Jira issue body, and a PR description state the verified fact directly.

A completed result the source already states stays direct, such as "Deployment failed" or "Approved." Hedge the author's read, such as "this failed" or "X is the problem."

| Avoid | Example |
| --- | --- |
| This failed | It looks like this failed |
| X is the problem | Could X be causing this? |
| Do X | Should we do X? |

This section does not replace vivid wording (§3). Place the question last (`SKILL.md` §3).

## §5 Audience

Change length and directness. Do not add an opinion the source does not contain (§2, §7). A hedge (§4) may lower the stated certainty of an observation.

| Audience | Adjust |
| --- | --- |
| Close coworker | Cut explanation of context they share |
| Manager / senior | State the purpose and the ask. Critique the system or outcome, not a person's motive |
| Unfamiliar / executive | Cut tangents first. Keep at most two concrete specifics from the source |

## §6 Work references

Do not bury a ticket ID inside a sentence ("I fixed PROJ-123 in auth"). State the ID in its own sentence. Link form: [links.md](links.md).

## §7 Never invent

Do not add a personal experience, opinion, commitment, or emotional reaction that the source does not contain. If context is missing, keep the source's uncertainty.
