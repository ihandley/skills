# 06: Move open contexts out of checkouts

**What to build:** The first use in a checkout that still has a local store moves its open contexts, session files, and suggestion hashes into the home store. Each context keeps its name, lease, and pause, and gains that checkout's origin as its label. A name already taken, a session file already present, or a corrupt file stays in the checkout, is reported again later, and is never read or written. Closed and archived files stay where they are. After that, only the home store is read.

**Blocked by:** 01 Capture a named context in the home store

**Status:** ready-for-agent

- [ ] The first hook event or command in a checkout that still has a local store moves that checkout's open contexts, session files, and suggestion hashes into the home store
- [ ] A moved context keeps its name, its lease, and its pause, and its repo label is that checkout's origin URL
- [ ] A workspace with several checkouts imports each checkout the hook was given
- [ ] When the open name is already taken in the home store, the checkout file stays. Later commands that see that checkout report it, and they do not read or write the leftover
- [ ] A session file that already exists in the home store is kept, and the checkout copy is reported the same way
- [ ] A corrupt context file stays in the checkout, is reported, and is not read or written
- [ ] Closed contexts and archived files in the checkout stay there
- [ ] When the same suggestion hash exists in both places, a declined record wins over an accepted one, and an accepted one wins over an offered one. Otherwise the home record stays
- [ ] After the move, commands read the home store only
- [ ] A second command started during the move waits until the move finishes, then reads the home store
