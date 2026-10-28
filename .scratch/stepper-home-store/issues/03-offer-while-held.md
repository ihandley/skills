# 03: Offer another context while one is held

**What to build:** A concrete list of work is offered with a proposed name even when this session already holds a list. The proposed name is never the sitting's name. Accepting captures that list alongside the ones you hold. Declining it keeps that candidate from being offered again, in any checkout.

**Blocked by:** 02 Hold more than one context in a session

**Status:** ready-for-agent

- [x] A candidate list is offered while the session already holds a context, and the offer asks once and includes a proposed name
- [x] The proposed name is free among open contexts, and it is never `pr-queue`
- [x] Accepting the offer captures that name and leases it alongside the contexts the session already holds
- [x] Declining a candidate records the decline in the home store, and that same candidate is not offered again from any checkout
- [x] A candidate that has already been offered or accepted is not offered again
- [x] A paused context does not suppress a new offer
