## What it does

Ticketer creates or updates a ticket in Jira or GitHub Issues while a CLI enforces your team's rules. The agent gathers the details and talks to you. The CLI checks the draft against your team config, shows you exactly what will be filed, and hands back the call to make.

The constraint is that the agent cannot file without your confirmation of the exact rendered draft. The CLI refuses a required field left empty, a malformed label, a missing template section, a description that repeats its acceptance criteria, and a value the tracker does not allow. It never contacts the tracker or holds credentials. The agent runs the tracker call with its own tools.

## When to reach for it

Type `/ticketer`, or the agent reaches for it when you ask to file, open, or edit a ticket, bug, or issue.

Reach for it when the ticket must follow team rules: required fields, labels, a parent ladder, an issue-type template. It is the wrong tool for reading, searching, commenting on, or transitioning a ticket. Use the tracker's own tools for those.

## Common questions

**Where do team rules live?**
In provider configs in `~/.config/ticketer/`, named by provider: `jira.toml`, `github.toml`. `~/.config/ticketer/mappings.toml` maps a directory, a git remote, or both to one of them. The longest matching path wins, and a remote entry applies only when no path matches. An entry can carry an `overrides` table for a repo, labels, or extra fields. A `.ticketer/team` file in a repository still works and wins over the mappings.

**What happens in a directory that is not mapped?**
Nothing is filed and there is no default. The agent asks which provider config to use, or whether to create one with `ticketer.py init`. It saves the answer with `ticketer.py map add`, so it does not ask again.

**Can a field be required for only one issue type?**
Yes. List the fields under `[required_by_type]` in the team config, keyed by issue type, for example `Bug = ["customfield_10568"]`. They apply on top of `required`, and the match ignores case. A `[required_for]` entry replaces `required` for that issue type. `required_by_type` still adds its fields.

**Where does the parent ladder live?**
In the Jira provider config, next to the parent allow-list. A Jira config with no parent ladder keeps the previous parent behavior.

**What does the confirm line show for a parent?**
The parent's key, issue type, summary, and status name. Nothing is filed until you say yes.

**What happens in a GitHub-mapped directory?**
Filing is unchanged. A GitHub config cannot carry a parent ladder, and a GitHub-mapped directory does not inherit one.

**Which trackers work?**
Jira and GitHub Issues. Each is a small adapter, so another tracker is an added module.

**Does it need credentials?**
No. It emits an operation and a payload. The agent needs a tracker tool, such as the Atlassian MCP or the `gh` CLI.

**What Python does it need?**
3.11 or newer. On an older interpreter it exits with the exact command to rerun under a newer one.

**Is the confirmation gate a security control?**
No. It stops an agent that forgets to ask. An agent set on bypassing it could fabricate the token. A host approval prompt on the tracker tool is the hard guarantee.

**What does verify check?**
After the ticket is filed, the agent reads it back and the CLI compares the fields to the draft. A dropped component or label shows up as a mismatch. Free-text description content is checked only for being non-empty, since trackers re-render it.

## It's working if

- The agent shows you a rendered draft and waits for a yes before anything is filed.
- When a parent ladder applies, that draft shows the parent's key, issue type, summary, and status name.
- A search that has to sit under a parent type still shows at most 10 matches, with a note when more matches exist.
- A GitHub-mapped directory files as it does today.
- A draft missing a required field comes back with a specific error, and the agent fixes it instead of filing anyway.
- Labels reach the tracker in lowercase kebab-case.
- After filing, the agent reports the ticket reference and either confirms the fields match or names the one that does not.
