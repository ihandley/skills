# A sitting walks open pull requests and the user strikes the item

The ledger held ticket-only rows, drafts, and merged or closed pull requests, none of which `qpre` can walk, and the loop had no word from `qpre` about how a walk ended.

## Decision

- The ledger holds only open, non-draft pull requests the user has not approved on the current head. In Review links come first, in Jira rank. Then pull requests updated in the last 7 days, newest first.
- The user's own pull requests stay. A bot's pull request stays only when an In Review ticket links it.
- An In Review ticket with no such pull request is a count beside the quiet count.
- `pr-queue` captures and stops. Start runs `qpre`. Quitting `qpre` leaves the item active.
- `qpre` writes one outcome line (`posted`, `clean`, or `partial`) and does not know the ledger. The loop reads that line and speaks `posted`, `clean`, or `unfinished`. It never reads findings.
- The loop asks the user to strike or do something else. A strike verifies the item with the outcome and the user's decision. The next item is briefed and `qpre` waits for start.
- The backlog stays a table outside the ledger. Naming a row runs `qpre` and captures nothing.

## Considered options

- Strike automatically on `posted`. Rejected: a posted review can still need a second pass, and the decision belongs to the user.
- Let `qpre` write to the ledger. Rejected: it would couple the walk to the loop, and the findings would leave the terminal.
- Keep ticket-only rows as reminders. Rejected: a row the loop cannot start is a prompt it cannot answer.

## Invariants

- A missing outcome line is a missing outcome, and the loop still prompts.
- `pr-queue` never starts `qpre` itself.
