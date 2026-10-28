# 05: Roll a finished sitting

**What to build:** `/pr-queue` uses the reserved name. An unfinished ledger this session holds is left as it is. An unfinished ledger nobody holds is attached. A finished ledger this session holds, or that nobody holds, is closed and a new sitting is captured. A ledger another session holds stops the run and names that session. A blocked or deferred item keeps the sitting in place. The backlog stays outside the ledger.

**Blocked by:** 02 Hold more than one context in a session

**Status:** ready-for-agent

- [x] `/pr-queue` captures and continues the context named `pr-queue`. A capture outside that skill uses some other name
- [x] An unfinished `pr-queue` this session holds is reported as already there, and no fetch runs
- [x] An unfinished `pr-queue` with no lease is attached to this session, and no fetch runs
- [x] A complete `pr-queue` held by this session, or held by nobody, is closed and a new sitting is captured from a fresh fetch
- [x] A `pr-queue` held by another session stops the run and names that session
- [x] A context is complete when every item is verified or cancelled and at least one item is verified. A blocked or deferred item leaves the sitting in place
- [x] A finished context with any name other than `pr-queue` stays leased until you close it
- [x] The backlog is not written into the ledger
- [x] Attaching or rolling `pr-queue` leaves the session's other contexts leased
