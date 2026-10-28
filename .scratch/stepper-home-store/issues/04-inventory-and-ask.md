# 04: Show every open context, and ask which one to change

**What to build:** Asking for status with no session shows every open context and who holds it. When your words name the sitting, a pull request, or a list, that context is the one that changes. When they do not, the agent asks once before it changes anything.

**Blocked by:** 02 Hold more than one context in a session

**Status:** ready-for-agent

- [x] Status with no session lists every open context in the home store, and for each one the session that holds it or that it has no lease
- [x] Words that name the sitting, a pull request, or an accepted list name select that context for a state change
- [x] When a message asks for a state change and names no context, the agent asks once which context and waits
- [x] The agent does not choose a context from which one changed most recently, or from which checkout the session is in
- [x] A brief spoken after a change covers the context that changed
