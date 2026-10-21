# Replace

The user explicitly says to drop this list or replace it. An inference that priorities changed is not that request. Another session's list stays. A corrupt context stays in place. Do not delete `.stepper/` for the repo, and do not pick a new context id to get around a corrupt file.

**Drop.** `drop` archives the list this session holds, without marking leftovers verified, and releases the lease. The session file stays. `capture` the new list with the same `--session` and `--root`.

**Replace.** `replace` takes the new outstanding items in one command. Items the user did not keep are cancelled. They are not left active, pending, or blocked, and they are not verified.

Done when `status` shows the replacement list, or no list after a drop. The brief matches that state.
