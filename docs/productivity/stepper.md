## What it does

Stepper keeps an ordered list of work in front of you and stays on the active item until that item is done. A chat may hold several of those lists. When you move to start something else, it restates what is done, what is left, what is blocked, and where the current item sits.

The list is temporary working memory for one stretch of delivery. The agent holds the order, including who you are waiting on. You decide when to wait, when to skip, and when the list itself is wrong.

## When to reach for it

Type `/stepper`, or the agent reaches for it when a reply contains a concrete list of remaining work, when you ask what is left, when you ask what is open (the index), or when you say to drop or replace the list.

Reach for it when you want to walk one feature through to the end without losing the thread. It is the wrong tool for learning a subject (`pair`) or for a ticket backlog.

## Common questions

**Where does the list live?**
In `~/.stepper` on this machine, outside any checkout. The `Stepper session:` line names the checkout. Commands pass that path as `--root` so a list about one repo can record that repo's origin. The checkout itself gains no store. The skill directory is refused as a checkout. The repository that contains the skill is a normal checkout.

**Does a state change print the whole list?**
No, the short form is the default. A state change prints only the four brief parts: done, left, blocked, and position. Add `--full` to get the whole store. `--brief` is still accepted and does nothing.

**What happens when the active item is blocked?**
Stepper recommends waiting, and says why. You can skip to the next item when that item does not depend on the blocked one. Skipping is available. Waiting is the recommendation.

**Can I throw the list away?**
Yes, when you say so. Dropping archives it without marking the leftovers done. Replacing swaps the outstanding items in one step. Another chat's list stays put.

**Will I hear the brief twice?**
No. A turn that already briefed or changed the list gets no reminder. When a reminder does follow a reply, its sentence ends with "Add nothing," and the agent adds nothing under it.

**What follows an ordinary reply?**
The reminder. It names the active item, the top-level count, and the rule to stick, and it tells the agent to add nothing. Done, left, blocked, and position show up when you ask what is left, when the list changes, or before you start something else.

**Does "verified" mean the tests passed?**
It means the agent stored a non-empty note. You still have to trust, or check, that the note is true.

**What happens to a list stored in the checkout?**
The first command or hook in that checkout moves its open lists into `~/.stepper`. Each one keeps its name, who holds it, and whether it is paused, and records that checkout's origin. A name already taken, a session already stored, or a damaged file stays in the checkout and is reported. Closed lists stay where they are.

**Can two chats share one list?**
No. The chat that starts the list holds it. Another chat can take it only when you ask to continue that work there.

**What if more than one list is open?**
`list` is the index of every open list. The index is newest local day first, then by name when the day is the same. Each row is the name, the day it last moved, how far the top-level items are, a lease word, and one line about the work. The lease word is `here` when this chat holds it, `elsewhere` when another chat does, and `free` when nobody does. A paused list keeps that word and adds `paused` in the same cell. A finished list stays, with the line `complete`. A closed list is left off. The repo and the chat id are left off the row. A damaged file or a leftover in the checkout is still reported with that index.

`status` is the item table for one list. With no name, that is the list this chat holds. When this chat holds several, you are asked which name. Naming a list shows its items and leaves the hold where it is.

**Which commands can I ask for?**
track, add, focus, verify, block, unblock, skip, defer, cancel, pause, resume, replace, drop, attach, list, and status. Asking what is left, and naming no list, is the brief for the list this chat holds.

**Can it offer another list while one is already open?**
Yes. The offer names a free list and never uses `pr-queue`. Saying yes tracks that list beside the ones you already hold. A paused list does not hide the offer. Saying no keeps that candidate from being offered again.

## It's working if

- After you accept a list, the agent starts at the first item and stays there.
- A blocked item comes back as "wait" before any offer to skip.
- An ordinary reply is followed by the reminder: the active item, the top-level count, the rule to stick, and "Add nothing." Nothing follows that line. The four parts wait for a request for what is left, a list change, or a new start.
- Starting something new gets the brief first: done, left, blocked, and where you are.
- Asking what is open shows one row per open list, with the day, the progress, a lease word, and one line.
- Asking for status shows each item on its own row.
- Saying the list is wrong archives it or replaces it, and the next item table matches that.
- A second list is offered by name while the first is still open, including when the first is paused.
