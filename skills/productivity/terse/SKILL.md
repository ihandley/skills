---
name: terse
description: >-
  Rewrites or drafts Slack, email, Jira, Confluence, and pull-request text to
  minimize length and maximize signal. Use when rewriting pasted text or
  drafting those media. Not an existing file or code. Use compressor or deslop.
compatibility: Requires Python 3
metadata:
  author: ian.handley
---

## Scope

These rules bind one outward draft: a Slack message, an email, a Jira description, a Confluence page, or pull-request text. The conversation about that draft stays ordinary speech. When the draft is delivered, these rules stop, including on the next turn. While understand or pair owns the turn, that skill owns the speech for the whole turn.

## §1 Objective

Minimize length and maximize signal. Keep the decisions, facts, uncertainty, and requests the reader needs. Keep one clause of rationale only when the request cannot be acted on without it. Delete alternatives, mechanism, and pedagogy unless the loaded mode requires them or removing them would make the text impossible to act on. Omit what they know. An acronym is a word this audience already says. When the author would not expect them to know it, use the name they say, once, in this message. A shorten request deletes optional rationale instead of repacking it. Keep the source's certainty, except a hedge the loaded mode requires.

## §2 Workflow

When rules conflict, apply the user's explicit instruction, then the loaded mode, then these core rules, then the loaded voice file.

1. Identify the medium; read matching [`modes/`](modes/) file, else [`modes/default.md`](modes/default.md). Ask only when plausible media require different structure or platform syntax.
2. If the draft mentions tickets, repos, PRs, Confluence pages, URLs, or people/channels to mention → also read [links.md](links.md).
3. Load the first existing voice file: `~/.claude/terse-voice.md`, then `<repo-root>/.claude/terse-voice.md`, then [voice.md](voice.md). Apply it where no higher-priority rule conflicts. Preserve its word choice, certainty, contractions, fragments, humor, and stated opinions.
4. Preserve original facts, uncertainty, gratitude, apology, and greeting. A sign-off stays unless it is filler or the request ends the prose. Reshape the request and delete praise as §3 says.
5. Rewrite the outward draft with §3-§7, medium conventions, and any loaded link rules. When another active skill requires a structure or visual, preserve it and apply these content rules within it. Do not apply the loaded mode's template.
6. Read [anti-ai-tells.md](anti-ai-tells.md); scrub remaining LLM tells in the prose.
7. Apply the final check (§8).

Return only the rewritten text unless the user asks for commentary or alternatives.

## §3 Writing

- Order the opening by what the reader can already interpret. When the result names something the reader does not have yet, one sentence of situation introduces it, then the result, then the consequence. Each sentence starts from a noun the previous sentence made available. The consequence reuses the situation's verb. The result leads when its nouns are already known, or when the reader may stop after one sentence. Keep that chain in one paragraph. The situation stays one sentence.
- The request is the last sentence of the prose. It asks the reader to do one finished action and addresses them as you. The verb names work they can complete. This wins over a voice rule that turns the request into a poll, a referral, or a second easier ask. Hedge a diagnosis in its own sentence, and only a cause the source already states. A labeled block of identifiers may follow the request. A sign-off does not.
- A heavy token appears once, in the sentence where the reader uses it: an address, a port pair, a long id, an ARN, an error string. Write an endpoint as `host:port`, or `host:port/port` for two ports. A count stays in the sentence. One id may stay in the sentence. Two or more ids or bare numbers go in one labeled block at the end of the message, after the request when there is one. The sentence points at that set by count.
- Put every question after its context.
- Concrete verbs. Active voice when the actor matters.
- Plain language ("investigate," not "perform an investigation").
- Cut throat-clearing and commentary about writing.
- Preserve code, commands, paths, identifiers, error strings, and quoted UI text exactly.
- A connective only when it shows cause, contrast, or sequence.
- Contractions and fragments only when natural in the medium.
- Use headings for distinct sections and bullets for parallel items.
- Gratitude thanks someone for an action. Praise evaluates their work, judgment, skill, effort, or the quality of a result. Delete praise even when it is specific or sincere. Approval is a decision (`Approved.`), not a compliment (`Looks good.`).
- One primary idea per sentence. Split independent thoughts. Avoid chaining with commas or semicolons. Em dashes and en dashes: §5.

## §4 Word choice

Drop these adverbs: simply, basically, essentially, actually, clearly, obviously, really, very, quite.

## §5 Punctuation

Never use the Unicode em dash (`—`, `\u2014`) or en dash (`–`, `\u2013`) anywhere in the complete response: rewrites, alternatives, explanations, acknowledgments, corrections. For a clause break, use a comma, a period, or a separate sentence. For a range, use a hyphen (`1-2`). Before return, pipe the complete response to `scripts/check-dashes` on standard input. If it exits non-zero, rewrite and run it again.

Never put parentheses mid-sentence. Delete optional parenthetical content. Put required parenthetical content in its own parenthesized sentence immediately after the sentence it qualifies.

## §6 Optional information

Before a qualifier, example, caveat, or aside: keep it only when removal would obscure the decision, request, owner, timing, evidence, or uncertainty. Otherwise remove it.

Delete optional information before shortening required information.

## §7 Economy

Remove a sentence, phrase, or word only when all of these stay unchanged: meaning; certainty, except a hedge the loaded mode requires; required context; requested action, owner, and timing; tone for the audience and medium; grammatical clarity and natural rhythm.

## §8 Final check

Before return:

- A required visual may precede the prose.
- No fact, qualification, or request was lost. A hedge the loaded mode requires is still present.
- `scripts/check-dashes` exits 0.
- [anti-ai-tells.md](anti-ai-tells.md) scrub applied.
