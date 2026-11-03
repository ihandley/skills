---
name: compressor
description: >-
  Compress an existing Markdown or plain-text document so padding comes out
  and the signal stays. Use when the user says "compress this skill" or asks
  to compress an existing file. Not an outward draft (Slack, email, Jira,
  Confluence, or pull-request text); that is terse's job.
argument-hint: <path or skill name>
---

The script is the only writer. A candidate stays off disk until it is accepted. Apply writes every file in the set, or it writes none. Leave git history untouched.

## Refuse the wrong artifact

The target is a document. An outward draft (Slack, email, Jira, Confluence, or pull-request text) goes to terse. Source code goes to deslop.

Done when the target is one document, or you have named the other skill and stopped.

## Read the pre-image

Read the document. A skill is a document whose set is the entry file plus the Markdown and plain-text files it links, including the files under a linked directory.

Padding is history, motive, restatement, or transition whose removal leaves the signal in place. Signal is a fact, decision, condition, obligation, or instruction the next reader would get wrong without. A trigger phrase in a skill description is signal too.

Done when you can name the padding, or you can say there is none.

## Stop when there is no padding

When you cannot name padding, stop. Tell the person the document is already dense. The files stay as they are.

## Compose the candidate

Remove the padding you named. The signal stays. Add nothing, except a Not clause on a skill description that names the sibling which would take the invoke.

On a `SKILL.md`:

- A hard constraint stays one bullet.
- Copy a payload the skill must reproduce verbatim.
- Judge the description for trigger recall. Shape it as What, then When, then Not. Collapse synonyms to one phrase. Aim no higher than `sibling_median` when the report includes one, unless a unique trigger phrase would be lost.

The candidate is one JSON object. Each key is a relative path and each value is the full proposed text. Skill paths are relative to the skill directory. A document path is the file's name, relative to that file's directory. Omit a file to leave it unchanged.

Done when every path you changed is in that object.

## Check

Run `python3 <this skill's directory>/compressor.py check <one path or skill name>` with the candidate on stdin. Stdout is one JSON object. Check writes nothing.

Done when you have the report: `ok`, `failures`, `diffs`, `words_before`, `words_after`, and, for a skill, `description_chars_before`, `description_chars_after`, `description_cap`, and `sibling_median`.

## Apply only a defended candidate

Apply when `ok` is true and you can name the padding removed, the signal that survived, and that nothing was added beyond the allowed Not clause. Run the same command with `apply` and the same candidate. A non-zero exit leaves every file as it was.

Done when apply exits 0, or you have named the defect and the files are unchanged.

## The next candidate answers one named defect

A later candidate answers one name in `failures`, or one signal loss you can point at in the diff. When you cannot name either, stop and report the defect.
