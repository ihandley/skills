# Tool map

`ticketer.py` emits a logical operation and a payload. It never names a platform tool. Execute the operation with the first available tool below. If none is available, say so and stop. Do not improvise a different call, and do not ask the user for tokens.

Payload keys are the tracker's own parameter names, so pass them through unchanged.

## Jira

| Operation | Atlassian MCP tool (Claude Code names it `mcp__<server>__<tool>`) | Fallback |
|---|---|---|
| `jira.get_project_issue_types` | `getJiraProjectIssueTypesMetadata` | none |
| `jira.get_create_fields` | `getJiraIssueTypeMetaWithFields` (pass `requiredFieldsOnly: false`) | none |
| `jira.create_issue` | `createJiraIssue` | none |
| `jira.edit_issue` | `editJiraIssue` | none |
| `jira.get_issue` | `getJiraIssue` | none |
| `jira.search_issues` | `searchJiraIssuesUsingJql` | none |

`jira.create_issue` payload keys are the tool's parameters. `additional_fields` holds labels, priority, components and custom fields. `parent` and `assignee_account_id` are top-level.

## GitHub Issues

| Operation | GitHub MCP tool | `gh` fallback |
|---|---|---|
| `github.list_labels` | none in the issue tools; use the fallback | `gh label list --repo R --json name --limit 200` |
| `github.create_issue` | `issue_write` with `method: create` | `gh issue create --repo R --title T --body-file F --label L --assignee A --milestone M` |
| `github.edit_issue` | `issue_write` with `method: update` | `gh issue edit N --repo R --title T --body-file F --add-label L` (see note) |
| `github.get_issue` | `issue_read` with `method: get` | `gh issue view N --repo R --json number,title,body,labels,assignees,milestone,url` |

`gh issue edit` adds or removes labels; it does not replace the list. When the descriptor says labels or assignees replace the whole list, remove the ones that are not in the draft with `--remove-label` and `--remove-assignee`.

Use `body_file` when the descriptor includes it. It avoids shell quoting problems with markdown.

## Metadata round trip

When `draft` returns `needs`, run each listed operation, then pipe the raw tool result into the `then` command. Run `draft` again. The result is cached, so this happens once per project or repo per day by default.

## Read-back

`submit` returns a `readback` operation. For a create, replace the `<...>` placeholder with the key or number the create returned. Pipe the result to `verify`.
