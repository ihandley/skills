---
name: ticketer
description: >-
  Create or update a ticket (Jira, GitHub Issues) with team rules enforced by a CLI. Use when the user
  asks to file, open, or edit a ticket, bug, or issue. Not for reading, searching, commenting on, or
  transitioning tickets; use the tracker's own tools for those.
compatibility: Requires Python 3.11+
metadata:
  author: ian.handley
---

# Ticketer

`ticketer.py` owns validation, the confirm gate, and the payload. You converse with the user and run the tracker tool call it emits. It never touches the network or credentials. Do not build a tracker payload yourself and do not skip a step.

Run `python3 <this-skill>/ticketer.py <command>`. Every command prints one JSON object. If it exits 3, the interpreter is too old: rerun with the command it prints. Do not work around it.

## Steps

1. **Locate.** `ticketer.py locate`. If `config_exists` is false, the directory is unmapped and there is no default. Ask the user which provider config to use (`providers` lists them) or whether to create one. To create one, run `ticketer.py init --provider <name> --tracker <jira|github>`, fill every `REPLACE_ME` with values the user gives you, and have them review it. Then save the choice with `ticketer.py map add --path <dir> --provider <name>`. Add `--remote owner/repo` to match by git remote instead. Never invent ids, keys, or field values.

2. **Collect.** Gather what the config's `required` list names. Ask for anything missing. For a description, use the section headings in `templates/<issue-type>.md`. If adjacent work or follow-ons are plausible, ask which to include before drafting.

3. **Draft.** Pipe the fields as JSON on stdin: `ticketer.py draft`. Keys are listed in the adapter (`adapters/jira.py`, `adapters/github.py`) as `DRAFT_KEYS`. Use `"operation": "update"` with `"key"` to edit.
   - Exit 2 with `errors`: fix them and draft again. Do not argue with a validator.
   - `needs` lists tracker calls to make first. Run each per [references/tool-map.md](references/tool-map.md), pipe the raw result into the `then` command, then draft again.

4. **Confirm.** Show `render` to the user verbatim and ask: **Proceed? (yes / no / edit)**. `edit` returns to step 3. `no` stops. Only a `yes` from the user in this conversation permits step 5.

5. **Submit.** `ticketer.py submit --draft <id> --confirm <id>`. Execute `descriptor` with the tool the tool map names. If no tool is available, say so and stop.

6. **Verify.** Run the `readback` operation (substitute the key or number the create returned) and pipe its result to `ticketer.py verify --draft <id> --result -`. Report the `ref` to the user. On `mismatches`, tell the user exactly what differs; do not retry silently.

## Hard rules

- Never run `submit` before the user said yes to the rendered draft.
- Never edit a draft file, cache file, or config to get past a refusal. Report the refusal.
- A new `yes` is needed after any change to the draft.
- Optional: `ticketer.py find-parent --query <text>` emits a search for an existing parent epic. Use it when the user wants the ticket under an epic and gave no key.

The gate stops a skipped confirmation. It cannot stop an agent that fabricates the token. A host approval prompt on the tracker tool is the only hard guarantee.
