## What it does

Ticketer creates or updates a ticket in Jira or GitHub Issues while a CLI enforces your team's rules. The agent gathers the details and talks to you. The CLI checks the draft against your team config, shows you exactly what will be filed, and hands back the call to make.

The constraint is that the agent cannot file without your confirmation of the exact rendered draft. The CLI refuses a required field left empty, a malformed label, a missing template section, a description that repeats its acceptance criteria, and a value the tracker does not allow. It never contacts the tracker or holds credentials. The agent runs the tracker call with its own tools.

## When to reach for it

Type `/ticketer`, or the agent reaches for it when you ask to file, open, or edit a ticket, bug, or issue.

Reach for it when the ticket must follow team rules: required fields, labels, a parent epic, an issue-type template. It is the wrong tool for reading, searching, commenting on, or transitioning a ticket. Use the tracker's own tools for those.

## Common questions

**Where do team rules live?**
In a TOML file at `.ticketer/<team>.toml` in the repository, or `~/.config/ticketer/<team>.toml` for you alone. `.ticketer/team` or `~/.config/ticketer/team` names the team. With no config, writes are refused. Run `ticketer.py init` to create a starter file, and commit it so teammates share it.

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
- A draft missing a required field comes back with a specific error, and the agent fixes it instead of filing anyway.
- Labels reach the tracker in lowercase kebab-case.
- After filing, the agent reports the ticket reference and either confirms the fields match or names the one that does not.
