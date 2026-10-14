# Jira

**P** is the active profile from `SKILL.md`. **T** is `on_merged.when_label` when the PR carries `skip_label`, otherwise `on_merged.otherwise`.

## Link

`key_pattern` in the branch or `headRefName` wins.

No match: `gh pr view <number> -R <repo> --json body,commits`. Grep `key_pattern` in `messageHeadline`, `messageBody`, and the PR `body`. Dedupe.

| Keys | Result |
|---|---|
| 1 | use it |
| 2+ | flag `ambiguous ticket mapping` |
| 0 | flag `no ticket mapping` |

## Rows

| State | Action |
|---|---|
| merged, not past, status is **T**, or **T** is `otherwise` and status is in `in_sync_statuses` | in sync |
| merged, not past, status is not that | safe: transition to **T**, delete the branch |
| merged, past, status is not **T** | safe: transition to **T**. The delete is judgment |
| closed, status is neither `on_closed_unmerged` nor a done status | judgment: transition to `on_closed_unmerged`, then `-d` |
| closed, status is done | judgment: flag the conflict |

## Writes

`transitionJiraIssue` by the status name. Discover the id once per distinct `(current_status, issue_type)`. A name that is not offered is a flag.

Audit comment, exact: `Auto-reconciled: PR <url> <merged|declined>.` via `addCommentToJiraIssue`.

`editJiraIssue` fills from `defaults`, using ids in `fields`. `sprint: open` is the current open sprint: `project = <project> AND sprint in openSprints()`. A sub-task skips every field in `subtask_skip_fields`. Fills other than story points go in the safe batch.

## Story points

One message for every ticket still missing `fields.story_points`. The values are 1, 2, and 3.

| Points | The change |
|---|---|
| 1 | One contained behavior. Little uncertainty. |
| 2 | A few parts, or a behavior plus real edge handling. |
| 3 | Several behaviors, or you are unsure how it fits. |

Judge from the PR title and the diff. Each row shows the key, the browse URL, and one sentence on why that number. The choice is 1, 2, and 3, recommended value marked **(Recommended)**, **Skip** last.

Write each chosen number with `editJiraIssue`. Print `<key> -> N.` **Skip** leaves the field unset and flags the row. Re-ask only a missing or ambiguous row.

Done when every ticket in the message has a written number or a flag.
