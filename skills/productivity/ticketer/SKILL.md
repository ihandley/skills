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

`ticketer.py` owns validation, the confirm gate, the search descriptor, and the payload. You converse with the user and run the tracker tool call it emits. It never touches the network or credentials. Do not build a tracker payload yourself and do not skip a step.

Run `python3 <this-skill>/ticketer.py <command>`. Every command prints one JSON object. If it exits 3, the interpreter is too old: rerun with the command it prints. Do not work around it.

Issue type names live in the provider config. This procedure uses parent ladder and parent allow-list for whatever those tables contain.

## Steps

1. **Locate.** `ticketer.py locate`. If `config_exists` is false, the directory is unmapped and there is no default. Ask the user which provider config to use (`providers` lists them) or whether to create one. To create one, run `ticketer.py init --provider <name> --tracker <jira|github>`, fill every `REPLACE_ME` with values the user gives you, and have them review it. Then save the choice with `ticketer.py map add --path <dir> --provider <name>`. Add `--remote owner/repo` to match by git remote instead. Never invent ids, keys, or field values. Done when `config_exists` is true, or the user has stopped.

2. **Resolve the issue type.** Ask for it when the user has not named one. A GitHub provider has no parent ladder. A config error that names `parent_ladder`, `parent_allow`, `parent_project`, `parent_match_field`, or `parent_match_type` on GitHub is reported and stops the filing. A Jira config with no parent ladder keeps today's parent behavior. Done when the issue type is known.

3. **Resolve the parent** when the issue type is a key on the parent ladder and this is a create, or an update that sets `parent`. An update that leaves the parent alone skips this step. A type that is not a key on the parent ladder skips it too.
   - A parent key the person already gave is the parent. Skip the classification question and the search. The draft in step 5 reads it and checks it. When that draft returns a parent read in `needs`, run it per [references/tool-map.md](references/tool-map.md), pipe the raw result into the `then` command, and draft again. A refusal is the answer: report it.
   - When every legal parent type has a parent allow-list, ask which key. Read each allow-listed issue and use its summary. When the person's words contain that summary, propose the key and still ask. Done when they name one key.
   - When the legal parent types split into a type that is not a key on the parent ladder and a type that is a key whose own parents are allow-listed, ask whether the work is a committed roadmap deliverable or internal. The person answers; the wording of the request does not. Roadmap searches the type that is not a ladder key. Internal searches the ladder-key type and passes the allow-listed parent keys as `--parent-key`.
   - When the only legal parent type is itself a ladder key, and that key's own legal parents split the same way, ask the same question. Roadmap searches that parent type and keeps hits whose parent is the type that is not a ladder key. Internal searches that parent type and keeps hits whose parent is the ladder-key type under an allow-listed parent. Resolve a parent type by searching that type, then pass the returned keys as `--parent-key` on the search of the child type. Jira's parent field takes keys. When the parent-type search reports more hits, ask the person to narrow before the child search.
   - Otherwise search the legal parent types in their configured projects, with no classification question.
   - When `parent_match_field` applies to the type being searched, pass `--match` with the draft's value for that field, or the provider default when the draft has none yet. When that search returns nothing, search again without `--match`, show those hits, and ask. Keep the value already chosen.
   - The search text is the summary when one exists, otherwise the phrasing the person used to ask for the ticket.
   - `ticketer.py find-parent --query TEXT --type TYPE [--match VALUE] [--parent-key KEY ...]` emits one tracker query. Run `descriptor`. Pipe the raw result to the same command with `--result -`. Show `shown` (key, summary, status), at most `cap`. When `more` is true, say that more matches exist. A hit whose own status is not Done stays in the result when its parent is Done. The query already hides Done hits. Leave the parent's status out of the query.
   - One hit is placed on the draft. The person still confirms before anything is filed. Several hits: the person picks. None: search the next parent level, then ask before creating. Create only issue types that are keys on the parent ladder. A type that appears only as a legal parent is not created.
   - A created parent is its own draft and its own confirm. Its parent is settled first. File on each yes. One parent is stored. When the work belongs to two deliverables, the person picks the one parent.
   - Done when a parent key is chosen, or the person has stopped. The draft in step 5 is what checks the read.

4. **Collect.** Gather fields for the ticket being drafted, after its parent is known. When that issue type has a `required_for` list, that list replaces `required`. `required_by_type` still adds its fields. Ask for anything missing. For a description, use the section headings in `templates/<issue-type>.md`. Set `project_key` to a project listed for that type in `parent_project` when the table has one. If adjacent work or follow-ons are plausible, ask which to include before drafting. Done when every field the draft will require is known.

5. **Draft.** Pipe the fields as JSON on stdin: `ticketer.py draft`. Keys are listed in the adapter (`adapters/jira.py`, `adapters/github.py`) as `DRAFT_KEYS`. Use `"operation": "update"` with `"key"` to edit. Include `issue_type` when an update sets `parent`.
   - Exit 2 with `errors`: fix them and draft again. Report a parent that cannot be read. The validator's answer stands.
   - `needs` lists tracker calls to make first. Run each per [references/tool-map.md](references/tool-map.md), pipe the raw result into the `then` command, then draft again.
   - Done when the draft exits 0.

6. **Confirm.** Show `render` to the user verbatim and ask: **Proceed? (yes / no / edit)**. The parent line shows the parent's key, issue type, summary, and status name. `edit` returns to step 5. `no` stops. When this ticket is later in a chain, `no` leaves tickets already filed and you report their keys. Only a `yes` from the user in this conversation permits step 7. A single search hit is not filed by itself.

7. **Submit.** `ticketer.py submit --draft <id> --confirm <id>`. Execute `descriptor` with the tool the tool map names. If no tool is available, say so and stop. Done when the tracker call has returned.

8. **Verify.** Run the `readback` operation (substitute the key or number the create returned) and pipe its result to `ticketer.py verify --draft <id> --result -`. Report the `ref` to the user. On `mismatches`, tell the user exactly what differs and stop the chain. A created parent is verified before the child is drafted. Then repeat from step 2 for the child.

## Hard rules

- Never run `submit` before the user said yes to the rendered draft.
- Never edit a draft file, cache file, or config to get past a refusal. Report the refusal.
- A new `yes` is needed after any change to the draft.
- With no parent ladder, `ticketer.py find-parent --query <text>` still emits today's parent search.

The gate stops a skipped confirmation. It cannot stop an agent that fabricates the token. A host approval prompt on the tracker tool is the only hard guarantee.
