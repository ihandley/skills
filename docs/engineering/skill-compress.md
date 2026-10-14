## What it does

`skill-compress` rewrites a `SKILL.md` and the support files it depends on so an agent can execute the skill densely. History, rationale, and padding come out. A rule stays when it changes what the agent does, asks, refuses, or sends.

The constraint is behavior. The rewrite is checked against an inventory of that behavior, and anything lost is put back. The frontmatter `description` is a separate pass: trigger phrases a sibling skill would otherwise steal, not the same cut applied to the body.

## When to reach for it

Type `/skill-compress`, or the agent reaches for it when you say "compress this skill", "make this SKILL.md denser", "cut the fluff from this skill", or "tighten this for the agent".

Reach for it on a skill whose instructions have grown past what the agent needs to run them. It is the wrong tool for Slack, email, or PR prose. Use `terse` for that. It is the wrong tool for AI residue in code. Use `deslop` for that.

## Common questions

**Will it drop a rule I still need?**
It lists everything that changes agent behavior before rewriting, then diffs the result against that list. Lost behavior is restored. Rationale that does not change behavior stays cut.

**Does the description get the same cut as the body?**
No. The body is cut for execution density. The description is cut for trigger recall, because it is loaded for every skill on every turn. A phrase stays when dropping it would let a different skill fire, or miss an unusual way you invoke this one.

**Will it invent a shorter workflow?**
No. It does not add steps, soften a hard rule, or widen what the skill does. A literal template or payload the agent must reproduce is copied unchanged.

## It's working if

- The report names what was cut, what was restored, and any intentional behavior change.
- The body is smaller, and the description character count is reported before and after.
- The phrases you actually use still select this skill, and a sibling does not take them.
- A second pass on the result finds almost nothing left to cut.
