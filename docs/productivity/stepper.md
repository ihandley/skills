## What it does

Stepper keeps a short list of outstanding commitments in view while an agent works through a long investigation. It remembers which item is active, and it brings the next one back after the current item is verified.

The constraint is that the agent cannot edit the list by hand. A small CLI owns the state, and a verified item needs a non-empty evidence note. That note records what the agent claims. It does not prove the claim.

## When to reach for it

Type `/stepper`, or the agent reaches for it when you ask to track acceptance criteria, remaining issues, or what's left.

Reach for it when a conversation is about to lose a short list of unfinished commitments. It is the wrong tool for a project plan, a ticket backlog, or a record of every intermediate step. Those stay in your issue tracker.

## Common questions

**Where does the list live?**
In `.stepper/` inside the repository you are working in. The skill install does not write that directory, and the first run adds it to the clone's local git exclude list.

**Can two chats share one list?**
No. The chat that starts the list holds it. Another chat can take it only when you ask to continue that work there.

**Does "verified" mean the tests passed?**
It means the agent stored a non-empty note. You still have to trust, or check, that the note is true.

**Can an acceptance criterion have sub-steps?**
Yes. Ask to track them under that item, for example under AC-3. Stepper keeps the parent in view, and the parent is not verified just because its sub-steps are finished. Overall progress counts the top-level items. `status --tree` shows the rest.

**What if I stop to understand something, or to pair?**
The list stays leased. While understand or pair owns the turn, the reminder stays quiet and the agent does not steer back to the list.

**Do I have to install hooks?**
No. Hooks add reminders when a session starts, when context is compacted, and when the agent is about to stop with items left. Without them, the commands still work when you or the agent invoke Stepper.

## It's working if

- After a long investigation of the first outstanding item, the agent comes back to the next one without you restating the list.
- A second chat does not change the list held by the first.
- Pausing, or asking an unrelated question, does not clear the list.
