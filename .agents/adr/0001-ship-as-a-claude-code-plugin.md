# Ship the skill set as a Claude Code plugin, and use skills.sh everywhere else

Skills in this repo are bucketed. `engineering/` and `productivity/` are promoted. `misc/`, `in-progress/`, and `deprecated/` are not. A plugin has to ship only the promoted set, which spans two folders.

Claude Code's `.claude-plugin/plugin.json` accepts `skills` as an array of explicit directories. That is how this repo lists promoted skills and leaves the other buckets out. `.claude-plugin/marketplace.json` makes the repo its own single-plugin marketplace, which is the documented Claude Code install, because this plugin is not in the official marketplace.

Codex's plugin manifest accepts `skills` as a single path and discovers `SKILL.md` files recursively under it. Pointing that path at `skills/` would also ship the buckets we keep out of the plugin. A flat directory of symlinks does not survive install, because Codex drops symlinks when it copies the plugin into its cache.

skills.sh already installs individual skills into Claude Code, Cursor, Codex, and other harnesses. It is the install path for every agent that is not consuming the Claude Code plugin.

## Decision

- Ship a Claude Code plugin (`.claude-plugin/plugin.json` plus `.claude-plugin/marketplace.json`), curated to the promoted set.
- Keep skills.sh as the installer for Cursor, Codex, and every other harness.
- Defer a native Codex plugin until Codex can select a curated subset of a bucketed tree.

## Invariants

- Every promoted skill has an entry in `.claude-plugin/plugin.json`'s `skills` array.
- `.claude-plugin/plugin.json`'s `version` tracks `package.json`. `npm run version` copies the package version into the plugin manifest.
