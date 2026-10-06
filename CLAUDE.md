Skills live in bucket folders under `skills/`:

- `engineering/`: daily code work
- `productivity/`: daily non-code workflow tools
- `misc/`: kept around, rarely used, not promoted
- `in-progress/`: beta, public on purpose, feedback wanted, not shipped in the plugin
- `deprecated/`: no longer used

Every skill in `engineering/` or `productivity/` (the promoted buckets) has a reference in the top-level `README.md` and an entry in `.claude-plugin/plugin.json`'s `skills` array. The Claude Code plugin ships exactly the promoted set. Skills in `misc/`, `in-progress/`, and `deprecated/` stay out of both.

Install commands are copied verbatim from [.agents/install-block.md](./.agents/install-block.md). `.claude-plugin/marketplace.json` makes the repo its own single-plugin marketplace. Run `claude plugin validate . --strict` after touching either manifest. The decision to ship a Claude plugin and leave Codex to skills.sh is in [.agents/adr/0001-ship-as-a-claude-code-plugin.md](./.agents/adr/0001-ship-as-a-claude-code-plugin.md).

Each skill entry in the top-level `README.md` links the skill name to its `SKILL.md`.

Each bucket folder has a `README.md` that lists every skill in the bucket with a one-line description, with the skill name linked to its `SKILL.md`. The promoted buckets' `README.md`s and the top-level `README.md` group entries into **User-invoked** and **Model-invoked**. The `misc/` and `in-progress/` READMEs use a flat list.

Skills in `engineering/` and `productivity/` also have a human-facing docs page at `docs/<bucket>/<skill-name>.md`. When you add, rename, or change the behaviour of a skill in those buckets, create or re-sync its docs page following [.agents/writing-docs.md](./.agents/writing-docs.md). A finished page carries four sections: **What it does**, **When to reach for it**, **Common questions**, and **It's working if**. Skills in `misc/`, `in-progress/`, and `deprecated/` get no docs page. A promoted skill removed outright keeps its page, marked archived (see `writing-docs.md`).

Every `SKILL.md` is either user-invoked (`disable-model-invocation: true` plus `policy.allow_implicit_invocation: false` in `agents/openai.yaml`, reachable only by the human) or model-invoked (model- or user-reachable). See [.agents/invocation.md](./.agents/invocation.md).

To (re)link every skill outside `deprecated/` and `misc/` into the local harness skill directories (`~/.claude/skills`, `~/.agents/skills`), run `scripts/link-skills.sh`. Each entry is a symlink into this repo, so a `git pull` keeps installed skills current. Re-run the script after adding, removing, or renaming a skill.

Shared vocabulary for the skills themselves lives in `GLOSSARY.md`. Rejections of a concept live as one file each under `.out-of-scope/`. See `SCOPE.md`.
