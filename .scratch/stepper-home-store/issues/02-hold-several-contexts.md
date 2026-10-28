# 02: Hold more than one context in a session

**What to build:** You can hold a second named list while the first is still open. Status and the reminder show every list this session holds, minus any you have paused. Closing or detaching one leaves the others. Ending the session releases every lease it holds. A crashed session keeps them until you say to take one.

**Blocked by:** 01 Capture a named context in the home store

**Status:** ready-for-agent

- [x] Capturing a second name while this session already holds a context leases both
- [x] Status for the session lists every context it holds, each with its name and its brief: done, left, blocked, and position
- [x] The reminder names every unpaused context this session holds, with those same four parts
- [x] Pausing one context removes it from the reminder and leaves the session's other contexts there
- [x] Closing or detaching one context leaves the session's other leases in place
- [x] Ending the session releases every lease that session holds
- [x] A session that stops without an end event keeps its leases. Taking one of them happens only after you ask for that context by name
