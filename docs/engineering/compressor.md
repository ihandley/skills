## What it does

Compressor takes an existing Markdown or plain-text document, or a skill, and takes the padding out while the signal stays. The candidate stays off disk until the checks pass. The script writes every file in the set, or it writes none, and it does not commit.

A shorter file is not enough. The write happens when the candidate is defended: the padding that came out, the signal that survived, and nothing added except a Not clause on a skill description.

## When to reach for it

Type `/compressor`, or the agent reaches for it when you ask to compress an existing document, including "compress this skill".

An outward draft (Slack, email, Jira, Confluence, or pull-request text) is [terse](../productivity/terse.md). Source code is [deslop](deslop.md).

## Common questions

**Will a shorter file always be written?**
No. The candidate is held until the checks pass, and it is applied only when the padding removed and the signal that survived can be named. A document that is already dense stays as it is.

**Does it commit?**
No. The script writes the files. You choose when the change is recorded.

**What about the other files in a skill?**
The script chooses the set from the links in `SKILL.md`. A support file with no padding can stay. A page the skill does not link, such as a human README, stays out. A failed check leaves every file as it was.

**Can the description change on its own?**
The description sits outside the word gate, so a description-only edit does not pass. It is judged for trigger recall, and it may gain a Not clause that names the sibling which would take the invoke.

## It's working if

- The files change only after the report is ok, and you were told the padding removed and the signal that survived.
- A failed check leaves every file as it was, and the report names the failure.
- An outward draft was handled by terse.
