---
name: terse
description: >-
  Rewrites or drafts Slack, email, Jira, Confluence, and pull-request text to
  minimize length and maximize signal. Use when rewriting pasted text or
  drafting those media.
compatibility: Requires Python 3
metadata:
  author: ian.handley
---

## §1 Objective

Minimize length and maximize signal. Keep the decisions, facts, uncertainty, and requests the reader needs. Keep one clause of rationale only when the request cannot be acted on without it. Delete alternatives, mechanism, and pedagogy unless the loaded mode requires them or removing them would make the text impossible to act on. Omit what they know; use their domain terms and acronyms without explanation. A shorten request deletes optional rationale instead of repacking it. Shorten only while meaning, readability, and tone hold. Keep the source's certainty, except a hedge the loaded mode requires.

## §2 Workflow

When rules conflict, apply the user's explicit instruction, then the loaded mode, then these core rules, then the loaded voice file.

1. Identify the medium; read matching [`modes/`](modes/) file, else [`modes/default.md`](modes/default.md). Ask only when plausible media require different structure or platform syntax.
2. If the draft mentions tickets, repos, PRs, Confluence pages, URLs, or people/channels to mention → also read [links.md](links.md).
3. Load voice (first existing file wins):
   - `~/.claude/terse-voice.md`
   - `<repo-root>/.claude/terse-voice.md`
   - [voice.md](voice.md) (skill default)
   Apply the loaded voice file where no higher-priority rule conflicts. Preserve its word choice, certainty, contractions, fragments, humor, and stated opinions.
4. Preserve original facts, uncertainty, and request force, except a recommendation hedge the loaded mode requires. Preserve gratitude, apology, and greeting. Preserve a sign-off unless a question ends the message (§3). Delete praise (§3) in every medium.
5. Rewrite with §3-§8, medium conventions, and any loaded link rules. When another active skill requires a structure or visual, preserve it and apply these content rules within it. Do not apply the loaded mode's template.
6. Read [anti-ai-tells.md](anti-ai-tells.md); scrub remaining LLM tells in the prose. Do not remove a section or visual another active skill requires.
7. Apply the final check (§9).

Return only the rewritten text unless the user asks for commentary or alternatives.

## §3 Writing

- Lead with the point, decision, or result.
- Put every question after its context. End with the final question. If a question ends the message, delete the sign-off.
- Concrete verbs. Active voice when the actor matters.
- Plain language ("investigate," not "perform an investigation").
- Cut repetition, throat-clearing, and commentary about writing.
- State a known fact directly unless the loaded mode says to hedge it. Keep a qualifier when the evidence is uncertain.
- Preserve code, commands, paths, identifiers, error strings, and quoted UI text exactly.
- A connective only when it shows cause, contrast, or sequence.
- Contractions and fragments only when natural in the medium.
- Use headings for distinct sections and bullets for parallel items.
- Keep source greetings, gratitude, and sign-offs unless they are automatic filler.
- Gratitude thanks someone for an action. Praise evaluates their work, judgment, skill, effort, or the quality of a result. Delete praise even when it is specific or sincere. Approval is a decision (`Approved.`), not a compliment (`Looks good.`).

## §4 Word choice

Drop these adverbs unless they change the meaning: simply, basically, essentially, actually, clearly, obviously, really, very, quite.

## §5 One idea per sentence

One primary idea per sentence. Split independent thoughts. Avoid chaining with commas or semicolons. Em dashes and en dashes: §6.

## §6 Punctuation

Never use the Unicode em dash (`—`, `\u2014`) or en dash (`–`, `\u2013`) anywhere in the complete response: rewrites, alternatives, explanations, acknowledgments, corrections. For a clause break, use a comma, a period, or a separate sentence. For a range, use a hyphen (`1-2`). Before return, pipe the complete response to `scripts/check-dashes` on standard input. If it exits non-zero, rewrite and run it again.

Never put parentheses mid-sentence. Delete optional parenthetical content. Put required parenthetical content in its own parenthesized sentence immediately after the sentence it qualifies.

## §7 Optional information

Before a qualifier, example, caveat, or aside: keep it only when removal would obscure the decision, request, owner, timing, evidence, or uncertainty. Otherwise remove it.

Do not rewrite text only to make it sound different. Every change must reduce reader effort, preserve required meaning, or fit the medium.

Delete optional information before shortening required information.

## §8 Economy

Remove a sentence, phrase, or word only when all of these stay unchanged: meaning; certainty, except a hedge the loaded mode requires; required context; requested action, owner, and timing; tone for the audience and medium; grammatical clarity and natural rhythm.

## §9 Final check

Before return:

- The opening paragraph contains the point, decision, or result. When another active skill supplies the layout, a required visual may precede that prose.
- If the text asks a question, no statement or sign-off follows the final question.
- No praise remains (§3).
- No fact, qualification, or request was lost.
- A hedge required by the loaded mode is still present.
- Alternatives, mechanism, and pedagogy are gone unless the loaded mode requires them, another active skill requires that visual, or the text would be impossible to act on without them. Rationale remains only when the request cannot be acted on without it.
- `scripts/check-dashes` exits 0 when the complete response is piped to it.
- [anti-ai-tells.md](anti-ai-tells.md) scrub applied.
