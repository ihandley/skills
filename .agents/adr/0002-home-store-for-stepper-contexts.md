# Stepper contexts live in the home directory

A context is one named list. Several checkouts, and a sitting that belongs to no repo, were sharing or blocking each other because the store was a `.stepper/` directory inside the checkout. The directory was the identity.

## Decision

- Store every context, session, and suggestion hash under `~/.stepper`.
- The checkout path on the hook line is the repo label's source. Capture records `git remote get-url origin` when a checkout is passed, and leaves the label empty otherwise. The label is not a filter.
- An open context's name is unique. Commands that change a context name it. Closing archives the context and frees the name.

## Considered options

- A `.stepper/` tree in each checkout. Two worktrees do not share a list, and a sitting that spans repos has nowhere to live.
- A database. One person, one machine, and a handful of open contexts do not need one. The unique name is the filename, and the lock is the one the CLI already takes.

## Invariants

- The checkout gains no tracking store.
- A second open context with the same name is refused, and the existing lease stays where it is.
