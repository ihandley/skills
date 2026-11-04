---
name: compressor
description: >-
  Compress an existing Markdown or plain-text document so padding comes out
  and the signal stays. Use when the user says "compress this skill" or asks
  to compress an existing file. Not an outward draft (Slack, email, Jira,
  Confluence, or pull-request text); that is terse's job.
argument-hint: <path or skill name>
---

The script is the only writer and the only judge of acceptance. A candidate stays off disk until a full walk returns no defects. Apply writes every file in the set, or it writes none. Leave git history untouched.

An outward draft (Slack, email, Jira, Confluence, or pull-request text) is terse's, and source code is deslop's. Pick that skill before this one runs.

## Inventory

Run `python3 <this skill's directory>/compressor.py inventory <one path or skill name>`. It writes nothing. A skill is the entry file plus the Markdown and plain-text files it links.

When `failures` is not empty, stop on that name. Do not name another skill.

The report lists, per file, `obligations`, `leftovers`, and `copies`, plus `cross_file_copies`. An obligation is a unit whose text must survive or be quoted. A leftover is a sentence the script could not classify as an obligation. You decide which leftovers are padding.

When `leftovers` and `copies` are empty in every file, stop. Tell the person the document is already dense. The files stay as they are.

## Propose one candidate

The candidate is one JSON object: relative path to full text, plus an optional `quotes` object. Omit a file to leave it unchanged.

- Delete the leftovers you judge to be padding.
- Delete extra in-file copies, leaving one occurrence. Leave cross-file copies in place.
- Keep each obligation verbatim. To drop one, put `"obligation text": "surviving sentence"` in `quotes`.
- Copy a payload the skill must reproduce verbatim.
- Add nothing, except one Not clause on a skill description that names the sibling which would take the invoke.

## Walk

Run `check` with the candidate on stdin. It writes nothing. The walk stops at the first failing rule and returns every defect of that rule, each with `rule`, `path`, and `span`.

When `ok` is true, run `apply` with the same candidate.

When it is not:

- Stop if `defects` equals the previous check's `defects`.
- Stop if this is a second answer to the same rule.
- Otherwise submit one candidate that clears every defect of that rule, then `check` again.

A stop leaves the files as they were. Report the rule and its spans.

## What a pass proves

A quote proves the surviving sentence exists. It does not prove the obligation moved there. Do not read an ok report as proof that signal survived.
