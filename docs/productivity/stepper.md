## What it does

Stepper keeps one ordered list of work in front of you and stays on the active item until that item is done. When you move to start something else, it restates what is done, what is left, what is blocked, and where the current item sits.

The list is temporary working memory for one stretch of delivery. The agent holds the order, including who you are waiting on. You decide when to wait, when to skip, and when the list itself is wrong.

## When to reach for it

Type `/stepper`, or the agent reaches for it when a reply contains a concrete list of remaining work, when you ask what is left, or when you say to drop or replace the list.

Reach for it when you want to walk one feature through to the end without losing the thread. It is the wrong tool for learning a subject (`understand`) or for a ticket backlog.

## Common questions

**Where does the list live?**
In `~/.stepper` on this machine, outside any checkout. The `Stepper session:` line names the checkout. Commands pass that path as `--root` so a list about one repo can record that repo's origin. The checkout itself gains no store. The skill directory is refused as a checkout. The repository that contains the skill is a normal checkout.

**What happens when the active item is blocked?**
Stepper recommends waiting, and says why. You can skip to the next item when that item does not depend on the blocked one. Skipping is available. Waiting is the recommendation.

**Can I throw the list away?**
Yes, when you say so. Dropping archives it without marking the leftovers done. Replacing swaps the outstanding items in one step. Another chat's list stays put.

**Does "verified" mean the tests passed?**
It means the agent stored a non-empty note. You still have to trust, or check, that the note is true.

**What happens to a list stored in the checkout?**
The first command or hook in that checkout moves its open lists into `~/.stepper`. Each one keeps its name, who holds it, and whether it is paused, and records that checkout's origin. A name already taken, a session already stored, or a damaged file stays in the checkout and is reported. Closed lists stay where they are.

**Can two chats share one list?**
No. The chat that starts the list holds it. Another chat can take it only when you ask to continue that work there.

**What if more than one list is open?**
Status with no session lists every open list and who holds it, or that nobody does. When you ask to change one and don't name it, the agent asks which one and waits.

**Can it offer another list while one is already open?**
Yes. The offer names a free list and never uses `pr-queue`. Saying yes tracks that list beside the ones you already hold. A paused list does not hide the offer. Saying no keeps that candidate from being offered again.

## It's working if

- After you accept a list, the agent starts at the first item and stays there.
- A blocked item comes back as "wait" before any offer to skip.
- Starting something new gets a status first: done, left, blocked, and where you are.
- Asking for status shows each item on its own row.
- Saying the list is wrong archives it or replaces it, and the next status matches that.
- A second list is offered by name while the first is still open, including when the first is paused.
