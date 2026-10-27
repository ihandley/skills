# Jira

Use this when `decide` reports `tracker` `jira` and `status_name` is set.

`cloudId` comes from `getAccessibleAtlassianResources` once per session. Pass it on every call.

1. `listJiraIssueTransitions` for the ref. If that tool is not already available, `discover` it and run it with `executeRead`. Match `to.name` to `status_name`. Pass that transition's `id` to `transitionJiraIssue`. The status name is not a `transitionName`.
2. `dependabot_review.py status --state state.json --transitions <file> --fields <file>`. The fields file lists `{id, name}` from the issue type's field metadata. The field named `Flagged` is the flag.
3. Run the `transition` it emits, then the `flag` edit through `editJiraIssue` on that field id. An empty `value` clears the flag.
4. The transition result is the status the issue landed in. It matches `status_name`. When a flag write was emitted, `getJiraIssue` shows that value.

Post the ticket comment with `addOrEditJiraIssueComment`.
