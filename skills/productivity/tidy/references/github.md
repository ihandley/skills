# GitHub issues

**P** is the active profile from `SKILL.md`.

## Link

Use `closingIssuesReferences` from Index B. When `key_pattern` is set, also accept one match in the branch name.

| Issues | Result |
|---|---|
| 1 | use it |
| 2+ | flag `ambiguous issue mapping` |
| 0 | flag `no issue mapping` |

An already-closed issue with `on_merged: close` is in sync.

## Rows

| State | Action |
|---|---|
| merged, not past, `on_merged: close`, issue open | safe: close the issue, delete the branch |
| merged, not past, `on_merged: close`, issue closed | in sync |
| merged, `on_merged: leave` | leave the issue. Delete the branch only when the row is not past |
| closed PR, `on_closed_unmerged: close` | judgment: close the issue, then `-d` |
| closed PR, `on_closed_unmerged: leave` | leave the issue. The branch delete is judgment |

## Writes

`gh issue close <n> -R <repo> --reason completed` for `on_merged: close`.

`gh issue close <n> -R <repo> --reason "not planned"` for `on_closed_unmerged: close`.

No field fills.

Done when each linked issue in the answered batch is closed or recorded as left alone.
