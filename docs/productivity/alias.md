## What it does

`alias` remembers a name, the ids behind it, and for a person their pronouns, then skips the lookup the next time that id is already stored.

Which tool fills which id lives in `~/.config/alias/config.yaml`. The skill does not know your chat, issue tracker, or directory. Nothing is added until you ask, and an id that is already stored is left alone.

## When to reach for it

Type `/alias`, or the agent reaches for it when you say "cache this", "remember this as X", or "what's the alias for Y", when you refer to a specific person, or before a lookup this cache might already hold.

Reach for it when the same person or resource would otherwise be looked up again. Use `ticketer` to file a ticket and `terse` to rewrite a message.

## Common questions

**Do the hooks have to be installed?**
Yes, once per harness. Without `hooks install`, a lookup is not skipped and a new id is not recorded. `get` and `add` still work. Codex can run those two and has no hook install. After the tool list in config changes, install again for Claude. Cursor reads the tool names from config, so a config edit is enough there.

**Where is the cache?**
`~/.alias/aliases.yaml`, unless `cache` in the config says otherwise. Copy `config.example.yaml` beside the skill to `~/.config/alias/config.yaml` and replace the tool names with yours.

**Will it overwrite a wrong id?**
No. An id that is already set stays. Correct it by editing the cache file. A lookup that matches the extract regex more than once, or not at all, is marked `_stub` and left for review. An entry you add yourself is never a stub.

**What if pronouns are missing?**
The agent uses the person's name and asks once in the session what to record. It does not use singular they for someone who is in the cache. A later session asks again while the field is still empty.

## It's working if

- A lookup whose id is already stored does not run.
- Referring to a person in the cache uses their stored pronouns.
- A new id is written only when the tool output matches the extract regex once.
- `get` on a miss prints `{"match": null}` and nothing is added until you say so.
