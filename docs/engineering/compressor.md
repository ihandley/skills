## What it does

Compressor takes an existing Markdown or plain-text document and takes the padding out while the signal stays. A skill is a document whose set is the entry file plus the Markdown and plain-text files it links. The candidate stays off disk until the walk is clean. The script writes every file in the set, or it writes none, and it does not commit.

The walk is the accept. The script inventories the document, then checks a candidate against a fixed list of rules and stops at the first rule that fails. You still decide which leftover sentences are padding. You no longer decide that the candidate is acceptable.

## When to reach for it

Type `/compressor`, or the agent reaches for it when you ask to compress an existing document, including "compress this skill".

An outward draft (Slack, email, Jira, Confluence, or pull-request text) is [terse](../productivity/terse.md). Source code is [deslop](deslop.md).

## Common questions

**Will a shorter file always be written?**
No. A candidate is written only when a full walk returns no defects. A document with no leftovers and no copies is already dense, and it stays as it is.

**What does a passing walk prove?**
That every listed obligation is still there, or is quoted by a sentence that is. A quote proves the surviving sentence exists. It does not prove the obligation moved there.

**What happens when a rule fails?**
The report names that one rule and every span of it. The next candidate answers that rule, and the walk starts again from the first rule. An identical defect list, or a second answer to the same rule, ends the run with the files untouched.

**Does it commit?**
No. The script writes the files. You choose when the change is recorded.

**What about the other files in a skill?**
The script chooses the set from the links in `SKILL.md`. A support file with no padding can stay. A page the skill does not link, such as a human README, stays out.

**Can the description change on its own?**
The description is outside the word count, so a description-only edit does not pass. It may gain one Not clause that names the sibling which would take the invoke. The cap is 1024 characters. The sibling median is reported and is not a rule.

## It's working if

- The files change only after the walk returns no defects.
- A failed walk leaves every file as it was, and the report names one rule and its spans.
- An identical defect list ends the run instead of looping.
- An outward draft was handled by terse.
