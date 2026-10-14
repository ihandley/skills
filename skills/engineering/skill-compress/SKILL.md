---
name: skill-compress
description: Compress an Agent Skill (SKILL.md + support files) for execution density without losing behavior — cuts history, rationale, and AI-padding while preserving every rule that changes what the agent does, asks, refuses, or sends. Optimizes for an LLM executing the skill, not a human reading docs. Use when the user says "compress this skill", "make this SKILL.md denser", "cut the fluff from this skill", "tighten this for the agent", or points at a bloated SKILL.md/command file.
argument-hint: <skill name or path to SKILL.md>
---

## Invoker contract

User supplies: skill name or path. Agent owns: reading, rewriting, diffing, reporting. Never ask the user to do the compression steps — just do them and report.

## Procedure

1. **§1 Read** — Read the full skill + every config/template/schema it depends on. Grep dependents (other skills, this repo) for references to this skill's `§N` labels, step names, markers, contracts, and sibling support files — confirm each still resolves after editing.
2. **§2 Inventory executable meaning** — List everything that changes what the agent does: triggers, required sequence, tool/field shapes, refusals, confirmations, config/team resolution, post-success actions, opt-in gates. Include the frontmatter description's WHAT / WHEN / NOT. Ground truth §6 diffs against — don't skip to save time.
3. **§3 Rewrite dense** (body):
   - Tables/code for shapes and enums (status values, confidence scales, field lists) — not prose bullets.
   - One-line rules. No dedicated section for a constant — fold it into the call it serves.
   - Number sections `§N` for cross-refs.
   - **Agent surface, not CLI cookbook** — no full `gh`/`git`/MCP command blocks. One-line shapes only where the agent would otherwise get the call wrong (required JSON fields, author filters, markers, body-file vs inline, flags that differ from defaults, tool name when several could apply). Intent + field list over shell script.
   - Exactly one blank line between blocks (after a heading, between paragraphs, before the next heading) — never two or more, never a trailing one at EOF. Not zero: parsing doesn't require it, but a maintainer's readability does. Targets *duplicate*/orphaned blanks left after a fold or cut, not the first one.
   - A heading followed by only one short paragraph, or a whole run of sequential-procedure headings — collapse to a bolded lead-in (`**Label:** clause`) or one numbered/bulleted list. Keep the heading only when it's independently cross-referenced or stands as its own browsable topic.
   - A bulleted list with exactly one item is a mis-formatted sentence — inline it.
   - A bulleted list of 3+ `**Label** - clause` pairs — collapse to a table (enum-with-detail shape), or one comma-joined line if the clauses are short. Exception: independent hard constraints checked one at a time (anti-goals, refusal conditions, a confirm checklist) — see below, that rule wins on conflict.
   - Independent hard constraints checked one at a time go the other way from most prose: one per bullet, never joined into a paragraph or a table row, even though the paragraph/table form is more character-dense. This is an agent-verification property (each item gets checked off individually), not human skimmability — it doesn't violate the density anti-goal below, and it overrides the label-clause-pairs rule above when both would otherwise apply to the same list.
   - Do **not** apply this body's token-min pass to frontmatter `description` — that is §4 (different metric).
4. **§4 Description** — Always run. Loaded every session for every skill in scope (trigger-matching); body loads once on invoke. Metric: **trigger/anti-trigger recall per character**, not body-style token-min.
   Shape, in order:
   1. **What** — one sentence: job + domain. No procedure, flags, `§` refs, or sibling internals.
   2. **When** — distinctive user phrases only. Collapse synonym clusters to one exemplar (`review my queue` covers `clear my review queue`). Keep a phrase iff dropping it would let a *different* skill fire, or miss an oddball invoke (`batch review`). An alias (`dbot`) stays only if users say it.
   3. **Not** — one clause naming the sibling that would otherwise steal the invoke (`Not a single named PR — use pr-review`). Required when the host repo treats overlap as partial (boundary-in-description).
   Strip if it only restates the body: batching mechanics, JSON fields, confirm strings, classify-then-dispatch narration.
   **Cap:** host-repo convention if one exists; else aim ≤ median `description` char length among sibling `SKILL.md`s in that repo; hard stop 1024. Over the aim-cap is a fail unless a unique phrase would be lost. Report before/after char counts in §13.
5. **§5 Cut / fold**:
   - History, "why we do this," narrated examples, restated cross-section laundry lists, motivational prose.
   - H1 that only restates the frontmatter `name`.
   - Duplicate hard-rules vs body — one source of truth.
   - "Never say X" if the confirm sequence already forbids it.
   - Tool maps / catalogs broader than actual scope (create-only skill → don't teach search).
   - Duplicate templates (e.g. a comment body that only wraps another template — say "wrap §N" once).
   - Human README drift — if the README isn't agent-loaded, shrink to a pointer or leave it alone; don't maintain two sources of truth.
6. **§6 Diff against inventory** — Check every item from §2 survived somewhere (body *and* description WHAT/WHEN/NOT); restore anything lost. Leave rationale cut — only behavior must survive. Unique trigger phrases belong in the description, not restored into the body.
7. **§7 Line-audit** — Per leftover paragraph: does this change agent behavior? No → delete. Yes but redundant with description/another `§`/a hard-rule → fold or delete once. Underspecified rules ("use 1–2 examples") → add a decision rule or "ask." A branch or checklist item with no observable condition gets a testable condition or is deleted. Quality targets such as readability, tone, and plain language stay as judgment.
8. **§8 Soft-signal restore** — Compare once more to the §2 inventory; restore only where thinning would cause misfire:
   - Exact MCP/tool identifiers when several tools could match.
   - Exact flags that differ from common defaults.
   - Exact search/match patterns — quotes, markers, idempotency strings.
   - Exact user-facing prompt/confirm strings and refuse/default choices.
   - Stack scope on any fallback (e.g. "Node-only repro") — non-matching stacks skip + ask, never silently apply the fallback.
   - Description: restore a dropped WHEN phrase only if §10 matching fails without it.

   Do not restore full command recipes or human-facing examples here.
9. **§9 Verbatim payloads** — Never paraphrase a literal template, schema, or exact payload shape the agent must reproduce in its own output (section-structure blocks, JSON shapes, controlled-vocabulary lists). Copy byte-for-byte. Compression targets prose around these, not the payloads themselves. This does not cover CLI/API usage examples (`gh`, `git`, MCP calls) — those are governed by §3's "agent surface, not CLI cookbook" rule and get thinned, not protected.
10. **§10 Trigger-scenario dry run** — Pick 2–3 concrete invocation phrases from the *pre-compress* description (including any synonym you collapsed). Walk the **compressed description alone** first: would it fire? would a sibling steal it? Then walk the compressed body — does it resolve unambiguously with no reference back to the original? Fix any that fail.
11. **§11 Idempotency check** — Would running this same pass again on your own output find anything left to cut? Should be near-zero — if not, recheck against §2 instead of cutting further.
12. **§12 Parity gap-check** — If this skill replaces a prior specialized skill/config, or a dependent elsewhere claims a contract this skill never actually stated, gap-check parity. Fix this skill/support files, or note the intentional delta explicitly in §13.
13. **§13 Renumber + report** — Renumber sections; update every `§N`/step reference in this skill and its dependents. Report: what was cut, what was restored, any intentional behavior change, body before/after size (lines or words), and description before/after char count — density must have improved, not just reformatted.

## Anti-goals

- Do not invent new workflow.
- Do not soften hard rules.
- Do not expand scope.
- Do not add examples unless they encode a payload shape the agent would otherwise get wrong.
- Do not optimize for human skimmability at the cost of executable density.
- Do not paraphrase a literal payload (§9).
- Do not thin genuine trigger coverage in the frontmatter `description` (§4). Synonym collapse is not thinning; dropping the only phrase that distinguishes this skill from a sibling is.
