---
name: tidy
description: Tidy local git branches against pull requests and the issue tracker in ~/.claude/tidy.yaml. Delete a branch only when the pull request already took its commits. Use when the user says "tidy" or "clean up my branches", or wants merged branches deleted and their issues updated.
---

Load the profile, classify every branch, then confirm. Mutations start after the safe-batch answer. Append one manifest run at the end.

## 1. Profile

Read `~/.claude/tidy.yaml`. **P** is `profiles[<profile>]`.

Done when **P** is loaded, `P.forge` is `github`, and `P.tracker.type` is `jira` or `github`. Any other state → stop and name the missing key. Point at `config.example.yaml` beside this skill.

`cloud_id: work_instructions` on a jira profile means the Jira cloud host in your work instructions. An empty `cloud_id` on jira → stop.

`--all` reads `P.repos_root`. Unset → ask for the directory.

## 2. Repos

| Invoke | Repos |
|---|---|
| no args | cwd |
| path | that path |
| `--all` | each child of `P.repos_root` that contains `.git` |

Skip a child that is not a repo. Gather every repo before showing a table.

Done when the repo list is fixed.

## 3. Classify

Per repo, together: `git fetch --prune`; `git status --porcelain` (warn, and continue); Index A; Index B. Read `manifest.json` before this (§5).

**Default.** `git symbolic-ref --short refs/remotes/origin/HEAD`. If that ref is missing, `gh repo view -R <repo> --json defaultBranchRef -q .defaultBranchRef.name`. Both fail → stop that repo and ask. Call the result `<default>`.

**Index A.** `git branch --format='%(refname:short) %(upstream:short) %(upstream:track)'`. The tip SHA is `git rev-parse <branch>` on every row that might be deleted.

**Index B.** `gh pr list -R <repo> --author @me --state all --limit 300` with JSON fields `number,state,title,url,mergedAt,isDraft,headRefName,headRefOid,labels,closingIssuesReferences,additions,deletions,changedFiles`. A result count equal to the limit is truncated. Refetch a higher limit before classifying.

**Unverified.** `gh` errors or returns no list. Mark the repo unverified and skip its deletes and tracker writes. A successful list with no PR for one branch is local-only.

| PR | Class |
|---|---|
| `MERGED` or `mergedAt` set | merged |
| `CLOSED`, no `mergedAt` | closed |
| `OPEN` | open |
| `isDraft` | draft |

Join `headRefName` to Index A.

**Past.** A merged PR whose local branch has any commit in `git log --oneline <headRefOid>..<branch>`, or a merged PR with no `headRefOid`. The tracker update can still be safe. The delete is judgment.

**Stale.** 30 days. A flagged local-only row includes `git log -1 --format='%ar' <branch>`. Older than stale is likely abandoned. A draft not updated within stale is flagged and skipped.

Link the issue, then apply that tracker's rows. Jira → [references/jira.md](references/jira.md). GitHub issues → [references/github.md](references/github.md).

Shared rows:

| State | Action |
|---|---|
| open | skip |
| draft, within stale | skip |
| draft, older than stale | skip and flag |
| no linked issue | flag, no tracker write |
| issue done or closed, PR open | flag, touch nothing |
| local-only, upstream `[gone]` | judgment: offer `-D` |
| local-only, ahead, no upstream, or upstream in sync | flag the age; delete only when the user picks it |

Done when every branch has a class, a tip SHA, and either one linked issue or a flag.

## 4. Confirm

Show one table: branch, issue, tracker state, PR state, local state, missing fields, proposed action. Then each flagged row with one recommendation.

**Safe** means merged, not past, not `<default>`, not the current branch, and not checked out in a dirty worktree. The safe batch is the tracker update, the branch delete, and Jira field fills other than story points. A past row updates the tracker only. Its delete is judgment.

1. Safe batch. Yes applies it, then prints one `git branch <name> <sha>` line per deleted branch, using the SHA from before the delete. No skips the batch. Empty moves on.
2. Story points, when **P** is jira and `require_story_points` is true. Every ticket still missing points, in one message. The list rules are in [references/jira.md](references/jira.md). Empty moves on.
3. Other judgment, one item, then stop. The recommended choice is first. **Skip** is last. Apply a non-skip answer before the next item. **Skip** records `flagged`.

A worktree (`git worktree list`, or `+` on the branch) comes out only when it is clean and the branch is safe.

Before each delete, `git rev-parse <branch>`. A SHA that differs from the table skips that branch.

`-D` deletes a safe merged branch. A closed unmerged branch uses `-d`. When `-d` refuses, say the branch is unmerged. Check out `<default>` before deleting the current branch, and leave the branch in place when that tree is dirty.

Done when the safe batch is answered, the points list is answered or empty, every judgment item is answered, restore lines for deleted branches are printed, and §5 has the new run.

## 5. Manifest

`~/.claude/tidy-manifest.json` holds the runs. Read it before classifying. Missing file means there are no prior runs. Append one run. Leave earlier runs in place.

Skip a branch or issue already named in `branchesDeleted` or `issuesChanged` from the last 7 days. Keep resurfacing `flagged`. An issue whose state changed again after that write is a later human action. Record `worktreesRemoved` only for a worktree this run removed.

```json
{
  "runAt": "<ISO timestamp>",
  "repo": "<path>",
  "profile": "<profile>",
  "branchesDeleted": [{"branch": "...", "sha": "..."}],
  "worktreesRemoved": ["<path>"],
  "issuesChanged": [{"key": "...", "from": "...", "to": "..."}],
  "flagged": ["..."]
}
```

Done when the new run is appended and names every branch deleted, issue changed, worktree removed, and row flagged in this run.
