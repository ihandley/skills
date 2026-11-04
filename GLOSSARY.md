# Glossary

Shared language for these skills. Add a term when a skill would otherwise spend a paragraph on a name that should be one word.

## Language

**Workflow**:
One repeating way a person gets a result, as they actually do it, including the tools and the hand steps.
_Avoid_: Process, routine

**Friction**:
Motion or attention that neither changes the result nor stops a bad outcome.
_Avoid_: Waste, inefficiency, control

**Control**:
A step that exists to stop a bad outcome.
_Avoid_: Check, gate, friction

**Redirect**:
The boundary at which another skill is the right reviewer.
_Avoid_: Handoff

**Release**:
Your decision that a control you perform is no longer worth its cost.
_Avoid_: Delete, remove, accept

**Quick**:
A friction change that uses tools already present. Removing or reordering steps counts.
_Avoid_: Day-1, quick win

**Overhaul**:
A friction change that replaces a tool, or adds a tool that is not present.
_Avoid_: Structural, rewrite

**Context**:
One ordered list of work with a single active item, and its own name while it is open. It may name the repo it is about.
_Avoid_: Instance, stepper instance, session

**Lease**:
A session's hold on one context. One context has one lease, and a session may hold several.
_Avoid_: Lock, owner

**Session**:
One chat with the agent.
_Avoid_: Sitting, conversation, context

**Paused**:
An open context with its reminders off.
_Avoid_: Blocked, held

**Reminder**:
The one sentence a hook shows for the active item.
_Avoid_: Brief, status

**Brief**:
What is done, what is left, what is blocked, and where the active item sits.
_Avoid_: Reminder, status

**Complete**:
A context in which every item is verified or cancelled, and at least one item is verified.
_Avoid_: Done, closed

**Closed**:
A context that has been archived and has no lease.
_Avoid_: Complete, deleted

**Sitting**:
One review of a queue, from capture until its ledger is done.
_Avoid_: Session, week

**Queue**:
Which pull requests are in this sitting, and in what order.
_Avoid_: Inbox, backlog

**Backlog**:
Open pull requests older than this sitting, kept outside the ledger.
_Avoid_: Queue

**Ledger**:
The context for one sitting.
_Avoid_: Queue, tracker

**Walk**:
One pass over a pull request.
_Avoid_: Review

**Outcome**:
How a walk ended. A review was posted, the walk finished with nothing to post, or the walk is unfinished. qpre writes it as one line, and the loop reads only that line.
_Avoid_: Done, status

**Strike**:
The user's decision that the active item is finished.
_Avoid_: Done, outcome

**Clean**:
A walk that finished with nothing to post.
_Avoid_: Empty, approved

**Unfinished**:
A walk left before it was posted or clean.
_Avoid_: Pending, paused

**Parent ladder**:
The issue types allowed as the parent of a given issue type.
_Avoid_: Hierarchy, parent rules

**Parent allow-list**:
The only issue keys that satisfy a parent type.
_Avoid_: Catalog, enabler list

**Document**:
An existing Markdown or plain-text file supplied by path. A shorter version does not have to be easier for a person to skim.
_Avoid_: Outward draft, AI-generated doc

**Outward draft**:
Slack, email, Jira, Confluence, or pull-request text being drafted or rewritten in the conversation.
_Avoid_: Document

**Signal**:
A fact, decision, condition, obligation, or instruction the next reader would get wrong without. A trigger phrase in a skill description is signal too.
_Avoid_: Meaning, content, behavior

**Padding**:
History, motive, restatement, or transition whose removal leaves the signal in place.
_Avoid_: Noise, fluff, prose

**Obligation**:
A listed unit whose text must survive or be quoted: a fenced block, list item, table row, heading, or a sentence that gives an order, holds inline code or an absolute URL, or that the script cannot classify.
_Avoid_: Meaning, content

**Quote**:
The surviving sentence a dropped obligation points at. It proves the sentence exists, not that the obligation moved.
_Avoid_: Meaning, content

**Candidate**:
A proposed replacement for a document, held until it is accepted.
_Avoid_: Draft, rewrite
