## What it does

`pr-queue` lists the pull requests to review this week and captures them as a sitting. It then walks them one at a time with `qpre` until you strike each item. It reads your team from `~/.claude/aliases.yaml`, takes the open sprint's `In Review` tickets first, then pull requests updated in the last 7 days.

The skill does not review the diff. `pr-queue` captures the list and stops. A later "start" runs `qpre` on the active item. When `qpre` exits the loop reads the outcome line, speaks it, and asks whether to strike the item.

## When to reach for it

Type `/pr-queue`. The agent will not reach for it.

Reach for it when you want the day's review queue. `/pr-queue backlog` is the open pull requests last updated more than 7 days ago. `all` on either command adds every other repo list on the team. For a review of one pull request you already have, use `pr-review`.

## Common questions

**Where do the people and repos come from?**
The `type: team` entry aliased "my team" in `~/.claude/aliases.yaml`. Authors are `members` and `qa`. The daily repos are `repos_active`. Sprint tickets are issues in an open sprint with status `In Review` whose Tech Domain is one of `jira_tech_domains`.

**What does a normal run show?**
One stepper list, not a table. In Review tickets stay in Jira rank, at any age. Recent pull requests are the ones updated in the last 7 days, newest first. The quiet count is every open pull request on the daily repos last updated more than 7 days ago, including pull requests you already approved. `all` counts the team's other repo lists as well. Your own open pull requests stay in the recent section. A pull request you have approved on its latest commit does not. Drafts, merged, and closed pull requests are never rows. A bot's pull request is a row only when an In Review ticket links it.

**What is on a line?**
`repo#number`, the title, the author's name, and days since the last update. A mark appears only when it applies: a repo list other than `repos_active` (`eol`, `lib`, and the other names shortened the same way) `asked` when you are a requested reviewer, `gone` when the author is not a known person, `conflict` when the pull request conflicts, or `red` when its checks are failing. The last three come from the same fetch as the queue. A line with none of these has no mark.

**What if an In Review ticket has no pull request?**
It is a count beside the quiet count ("2 without a pull request"), not a row. The same goes for a ticket whose only pull requests are drafts, merged, closed, or already approved by you.

**Who captures the list?**
`sitting open`. It applies the lease rules, calls `pr-queue` only when a fresh fetch is due, and `pr-queue` builds the lines, writes them into the stepper under the `pr-queue` context, and orders them free in one run. The agent only passes the Jira issues in and prints what comes back. A hand-written capture cost minutes in the first timed run, so the agent no longer writes one.

**What does start do?**
qpre needs an interactive terminal, so the agent tells you to run `sitting walk --session KEY --root PATH --stepper PATH --viewer LOGIN` there. For the active item the walk prints the four brief parts, runs `qpre` on its pull request with your terminal, and waits for it to exit. Quitting `qpre` (a non-zero or signal exit) leaves the item active and asks nothing. `qpre` has to write its outcome line for the pull request (`<outcome dir>/<org>-<repo>-<number>`, default `~/.qpr/outcomes`; override with `--outcome-dir` or `SITTING_OUTCOME_DIR`); the command to run is `qpre` unless `--qpre` or `SITTING_QPRE` says otherwise.

**What happens when qpre exits?**
The walk reads the one outcome line `qpre` wrote and says `outcome: posted`, `clean`, or `unfinished` (`partial`, `unfinished N`, and `unposted` all read as unfinished). It does not read the findings, which stay on the terminal. A missing line is `outcome: missing outcome`, never clean. It also says `approved: yes` or `no` for whether you approved the latest commit, from GitHub, so an unfinished outcome does not hide an approval. Then one key: `s` strikes the item (the outcome and approval become the evidence) and walks the next item, `k` keeps it active and leaves the walk, `q` or Ctrl-C leaves the walk with the item active, and any other key asks again. A question about the pull request stays in chat, outside the walk. The walk stops when no item is active.

**What does a strike do?**
`sitting strike --session KEY --root PATH --stepper PATH --evidence TEXT` verifies the active item with the evidence you give (the outcome and your decision), then prints the next item's four brief parts: `done`, `left`, `blocked`, `position`. It uses stepper's `--brief` form, so it never prints the whole store. The agent runs it instead of a raw `stepper verify`. `sitting brief` with the same session, root, and stepper arguments prints the four parts for the current sitting and changes nothing.

**How do I check the active item out locally?**
`sitting checkout --session KEY --root PATH --stepper PATH` (`scripts/sitting`, beside `pr-queue`) finds the clone of the active item's repository under `clone_roots` on the team record, leaves it on the pull request head, and prints `clone:` and `base:`. Diff against that base ref, not a local branch of the same name. A clone with uncommitted changes stops the command and is left alone. A missing `clone_roots` stops the run and names the key.

**What does backlog show?**
A table of those older pull requests you have not approved on the latest commit, newest update first. A row number runs `qpre` and captures nothing.

**What does a second `/pr-queue` do?**
`sitting open --session KEY --root PATH --stepper PATH --viewer LOGIN` (the In Review issues on stdin, as `pr-queue` reads them) decides it, so you apply none of these rules. It then prints the queue and the four brief parts (`done`, `left`, `blocked`, `position`) from stepper's `--brief` form, not the whole store. An unfinished sitting in this chat stays as it is, and nothing is fetched. An unfinished sitting nobody holds is attached to this chat. A finished sitting this chat holds, or that nobody holds, is closed and captured again from a fresh fetch. A sitting another chat holds stops the run and names that chat. A blocked or deferred item keeps the sitting. A finished context with any other name, and your other contexts, stay leased.

**Where does the Jira query come from?**
`pr-queue --print-jql` builds it from `jira_project` and `jira_tech_domains` on the team record, and prints the Atlassian cloud id and site URL stored there as `atlassian_cloud_id` and `atlassian_site`. The agent runs that command, searches Jira once with the printed id, and never reads the alias file or looks the site up. A missing key stops the run and names the key.

**What if it stops before the queue?**
The Atlassian connection or the GitHub connection is missing, or the stepper hook never named this chat. The session line arrives with the first tool result. Install the stepper hook when that line is absent after those calls.

**How is the printed list checked?**
`python3 skills/engineering/pr-queue/tests/test_pr_queue.py` runs the script on saved input, a Jira file and a GitHub JSON file, without calling GitHub or Jira. It compares the normal list and the backlog table to files in `tests/fixtures`. Any change to the printed lines fails it. The script needs Ruby 2.6 or newer and the `gh` CLI, as the skill's `compatibility` line says.

## It's working if

- The list matches the open sprint's `In Review` tickets in rank order, then pull requests updated in the last 7 days.
- A second `/pr-queue` leaves an unfinished sitting in place, and replaces a finished one.
- "Start" runs `qpre` with the full pull request URL, and the item stays until you strike it.
- After `qpre` exits you hear `posted`, `clean`, or `unfinished`, and no findings.
- No draft, merged, closed, or approved pull request is in the list.
- The quiet count arrives without those older pull requests being downloaded.
- The list is printed from searches that return pull requests. A search that comes back empty stops the run and names the query.
- The run prints its total time from the prompt to the list, and it stays under five minutes.
- `python3 skills/engineering/pr-queue/tests/test_pr_queue.py` and `test_sitting_open.py`, `test_sitting_strike.py`, and `test_sitting_checkout.py` pass with no network.
- A strike prints four lines (`done`, `left`, `blocked`, `position`), not the ledger.
- The run makes one Jira search with the stored cloud id and no site lookup.
