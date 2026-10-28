# 01: Capture a named context in the home store

**What to build:** You can capture a named list that is stored for you, outside any checkout. Passing a checkout records that repo's origin on the list as a label. Capturing a name that is already open tells you who holds it and leaves that lease where it is. Closing the list archives it and frees the name. Commands that change a list name it. The decision to use a home-directory store is recorded in an ADR.

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [x] Capturing a named context stores it in the home store (`~/.stepper`) and leases it to the session that captured it
- [x] The checkout where the command ran contains no tracking store afterward
- [x] The hook line carries the session key and the checkout path, and the session record is written in the home store
- [x] A capture given a checkout path stores that checkout's origin URL, as `git remote get-url origin` returns it, on the context. An omitted path, or a checkout with no origin, leaves the label empty
- [x] Status for that session shows the context's name, its repo label when one is set, and the brief: done, left, blocked, and position
- [x] The repo label is shown with the context. No command selects or filters contexts by it
- [x] Capturing a name that is already open fails, names the session that holds it, and leaves that context unchanged
- [x] Two open contexts with different names can carry the same items
- [x] Every command that changes a context takes that context's name
- [x] Closing a context archives it, drops its lease, and frees the name so a later capture can use it
- [x] An ADR in this repo's ADR directory records the home-directory store, and why it won over a per-checkout tree and over a database
