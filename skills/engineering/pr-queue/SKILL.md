---
name: pr-queue
description: List this week's review queue, the open sprint's In Review tickets and the last 7 days of team pull requests.
disable-model-invocation: true
---

Build the queue and stop. A `backlog` invocation does Record, Stop, and Backlog. Any other invocation does Record, Stop, Sitting, and then either stops or does In review, Fetch, Home, and List. `all` on either invocation widens the repo set. Later turns use what this invocation stored.

Call the Skill tool with `stepper` before any stepper command. The stepper CLI named in that skill is the one you run.

## Record

Read `~/.claude/aliases.yaml`. The **record** is the `type: team` entry aliased "my team". The **viewer** is the person aliased "me".

Resolve authors (`members` and `qa` to `ids.github`), `repos_active`, every other `repos_*` list, `github_org`, `jira_project`, and `jira_tech_domains`. The **scope** is `repos_active` plus those authors. `all` widens the repo set to every `repos_*` list; the authors stay. The record is the only source for these values. The sprint filter is the JQL below and nothing else on the record.

Done when each value is present and every author has `ids.github`. Anything missing: stop and name the key.

## Stop

Call `getAccessibleAtlassianResources` once and keep its cloud id and site URL. Call GitHub `get_me` once and keep its login. A missing MCP tool, a namespace that is not authenticated, or a failed call stops the run.

The viewer's `ids.github` equals that login. Any other result: stop and print both logins.

On a list invocation, copy `--session` and `--root` from the hook line that starts with `Stepper session:`. Read it from the prompt, or from the context attached to those MCP results. A line that is still absent then stops the run: say the stepper hook did not provide a session key.

Done when the cloud id, the viewer, and (on a list invocation) a session key are in hand, or the run has stopped.

## Sitting

The context name is `pr-queue`. A capture outside this skill uses some other name.

On a list invocation, run `status` with no `--session` and find the context `pr-queue`.

- Another session holds it: stop and name that session. Do not fetch.
- This session holds it and `complete` is false: say the sitting is already there. Do not fetch.
- Nobody holds it and `complete` is false: `attach` it to this session. Do not fetch.
- This session holds it, or nobody holds it, and `complete` is true: `attach` first when nobody holds it, then `close` it, and continue to a fresh fetch.
- No `pr-queue` context: continue. Capture uses `--context pr-queue`.

`complete` is true only when every item is verified or cancelled and at least one item is verified. A blocked or deferred item leaves the sitting in place. A finished context with any other name stays leased until the user closes it. Attaching or rolling `pr-queue` leaves this session's other contexts leased.

Done when the run has stopped, an existing sitting is in this session, or a finished sitting was closed and a fresh fetch is next.

## In review

A list invocation searches Jira with `searchJiraIssuesUsingJql`. Page with `nextPageToken` until `isLast` is true. Fields are `summary`, `assignee`, and `updated`. Keep the result order.

```
project = <jira_project> AND "Tech Domain[Dropdown]" in (<jira_tech_domains>) AND status = "In Review" AND sprint in openSprints() ORDER BY Rank ASC
```

Done when every issue from that JQL is held in rank order. A failed call stops the run.

## Fetch

One GraphQL search, then one quiet count. Repeat the same search with `pageInfo.endCursor` while `hasNextPage` is true. A failed call stops the run.

**Cutoff** is the calendar date 7 days ago, `YYYY-MM-DD`. **Scope** is `repo:ORG/name` for each repo in the repo set, plus `author:login` for each author, joined with `OR`.

Search query, with the key clause omitted when In review is empty. The first example is the shape: `updated:>=2026-10-20` means on or after that cutoff.

```
is:pr org:ORG ((is:open draft:false updated:>=CUTOFF (SCOPE)) OR KEY OR KEY)
```

The first call passes no cursor. Later calls pass `pageInfo.endCursor`.

```graphql
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 50, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title isDraft state updatedAt body headRefName headRefOid
        repository { name }
        author { __typename login }
        commits(last: 20) { nodes { commit { message } } }
        reviews(last: 50) { nodes { state author { login } commit { oid } } }
        reviewRequests(first: 20) { nodes { requestedReviewer { ... on User { login } } } }
      }
    }
  }
}
```

The **head** is approved when an `APPROVED` review's author is the viewer and its commit oid is `headRefOid`.

The quiet count is `total_count` from one search, `per_page=1`, and it is not paged:

```
is:pr is:open org:ORG updated:<CUTOFF (SCOPE)
```

`updated:<2026-10-20` means updated before that cutoff. Done when the search pages are held and the quiet count is that `total_count`.

## Home

**Link** an In review issue to a fetched pull request when its key appears as `<jira_project>-<digits>` in the head branch name, then in commit messages, then in the body. Each linked pull request is its own item. An issue with none is one ticket-only item.

A pull request has one home:

1. **In review** — an issue links it. Rank order, and the issue's order for its pull requests. Any age, any state. A Bot author stays.
2. **Recent** — open, not draft, `updatedAt` on or after the cutoff, repo in the repo set or author in the authors, not already at home in In review, author `__typename` is not `Bot`, and the viewer has not approved the head. The viewer's own pull requests stay. Newest `updatedAt` first.

Count Bot-authored pull requests in the fetched set that took neither home. A repo on `repos_active` has no list mark. Any other list mark is that list's name without `repos_`. A repo on several of those lists uses the first one in the file.

The **author** shown is the person's alias that contains a space, or the longest of those aliases. A login with no person stays the login. A ticket-only item uses the assignee display name, or `unassigned`.

**Age** is whole days from `updatedAt` (or the issue `updated`) to today, rendered `19d`.

**Marks** follow `repo#number`, and only when they apply: the list mark, `asked` when the viewer is a requested reviewer, and `draft`, `merged`, or `closed` for that state.

Item text is `<repo>#<number> <marks> · <title> · <author> · <age>`. Ticket-only text uses the issue key in place of `repo#number` and the issue summary as the title. The text has no URL.

Done when every In review issue and every Recent pull request has one home, in that order.

## List

Print `N quiet`, and ` · M bots` when the bot count is greater than zero. Then print each item's text on its own line. An empty home prints the quiet line and stops without a capture.

Capture in home order under `--context pr-queue`. The id is the issue key, or `<key>-<repo>-<number>` when the issue has a pull request. A Recent id is `<repo>-<number>` after characters outside `A-Za-z0-9` are removed from the repo. An id that does not start with a letter gets a `pr-` prefix. Each `--item` is `id | text | criteria`.

Criteria for an open, non-draft pull request: `Start runs qpre on https://github.com/<github_org>/<repo>/pull/<number>. Done when the user says the review is done. Quitting qpre leaves the item active.`

Criteria otherwise: `No qpre: <draft, merged, closed, or ticket-only>. Done when the user says this item is done.` A ticket-only criterion includes the site URL from the Atlassian call plus `/browse/<key>`.

Then `order` with every id as `--item`, in the same order, and every id as `--free`.

Speak `done`, `left`, `blocked`, and `position` from `status`.

Done when the lines are printed, every item is free, and the four brief parts match `status`. qpre has not been started.

## Backlog

Skip In review, the list, and stepper. The backlog is not written into the ledger. Fetch with the same GraphQL search and this query:

```
is:pr is:open org:ORG updated:<CUTOFF (SCOPE)
```

Page to the end. Keep a pull request when the repo is in the repo set or the author is an author, the author is not a Bot, and the viewer has not approved the head. Newest `updatedAt` first.

Print a table. Cells are plain text. Columns: row number, PR, title, author, age, approvals. The PR cell is `repo#number` plus marks. Age is days since `updatedAt`. Approvals is the count of `APPROVED` reviews. The heading is `Backlog · <count>`, and when every row has 0 approvals, add `· none approved`. Print `M bots` when Bot authors were left off.

Done when the table and the bot line are printed. qpre has not been started.

## Later

A later message uses the captured list or the printed table. It does not fetch again.

**Start** on a list runs `qpre` with the active item's pull request URL when that item's criteria say to start.

A **row number** on the backlog table runs `qpre` with that row's URL, rebuilt as `https://github.com/<github_org>/<repo>/pull/<number>`, when the pull request is open and not draft.

The user says the review is **done**: `verify` the active item with that evidence, then speak the four brief parts.

`skip` only when the user asks to skip. Quitting qpre leaves the active item active.

Done when qpre has been started for a startable item, or the item was verified, or a draft, merged, closed, or ticket-only item was named and qpre was not started.
