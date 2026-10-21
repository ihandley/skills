---
name: alias
description: Look up or save a cached name, id, or pronouns before resolving a person or resource. Use when the user says "cache this", "remember this as X", or "what's the alias for Y", when referring to a specific person, or before a repeated lookup for something this cache might already hold.
compatibility: Requires Python 3.11+. Hooks are installed separately for Claude and Cursor.
metadata:
  author: ian.handley
---

# Alias

The cache maps a name to ids and, for a person, pronouns. Which tool fills which id is config, in `~/.config/alias/config.yaml` (override with `ALIAS_CONFIG`). The script does not know the names of any chat, issue tracker, or directory. A published example is [config.example.yaml](config.example.yaml).

Run `python3 <this-skill>/alias.py <command>`. Every command prints one JSON object.

The cache file is a YAML subset: scalars, inline lists, and one nested map, `ids`. `alias.py` parses that subset itself.

## Referring to a person

If a session-start projection is already in context, use it. Otherwise run `alias.py get "<name>"`.

Use the entry's `pronouns` when you refer to that person. If the entry exists and `pronouns` is absent, use their name and ask once in this session what to record. Do not use singular they for a person who is in the cache. A later session asks again while the field is still empty.

## Configured tools

`hooks install` is required. Without it, lookups are not skipped and new ids are not recorded.

A tool binding names the tool, the query field, the entry type, the `ids` key, and `extract`: a regex with one capture group. When that id is already stored, the pre hook skips the tool call. The post hook writes the id only when the regex matches exactly once. Several matches, or none, stay a `_stub` for later cleanup. An id that is already set is left alone. Correct a wrong id by editing the cache file.

After the tool list in config changes, run `hooks install` again for Claude. Cursor filters tool names in the script, so a config edit is enough there.

```bash
python3 <this-skill>/alias.py hooks install claude
python3 <this-skill>/alias.py hooks install cursor
python3 <this-skill>/alias.py hooks status
```

Cursor's session-start context is not restored after compaction. Claude's is, including on compact.

## Get and add

Use these for an entry with no tool binding, and for pronouns. Ask before `add`. Do not add on your own.

```bash
python3 <this-skill>/alias.py get "<query>"
python3 <this-skill>/alias.py add <type> "<name>" pronouns=she/her ids.employee=E1 email=ada@acme.test
```

`get` prints `{"match": null}` on a miss. `add` fails when that type already has a matching name. Edit the cache file to change an existing entry.

Matching is case-insensitive. An exact match wins, and a longer alias beats a shorter one.

## Notes

- `_stub: true` marks an unreviewed lookup. Nothing added through `add` is a stub.
- Codex can run `get` and `add`. It has no hook install.
