## What it does

`pair` is the one way into teach-as-you-go work. You say what you are working on, and the same session either builds or explains. A change is building: a numbered plan you confirm, then one chunk at a time, and you write each chunk. A question is the portion loop: one explanation of the immediate gap, then a stop. The opening line says which loop this is, and one line flips it.

The agent does not edit a file until you ask for the full answer on the current chunk. Asking to skip the plan confirm does not skip it. The skill says `stop pairing` once and drops the controls only when you say those words.

## When to reach for it

Type `/pair`. The agent will not reach for it.

Reach for it when you want to make a change yourself while the agent navigates, or when you want to understand a codebase or any other subject one portion at a time. It is the wrong tool when you want the agent to implement the change. It replaces `understand`, which was the separate entry for the portion loop.

## Common questions

**What does `/pair` with nothing after it do?**
It asks what we are working on. Yesterday's thread does not take the turn. `/pair continue` resumes the journal's current thread and names its loop. With no thread, it asks what we are working on.

**How do I switch between building and explaining?**
"Explain <subject>" starts the portion loop on that subject. "Let's build" returns to the same chunk when a plan is confirmed, or starts the plan when none is. "Just write it" during a portion is a request to build, so it goes through the plan.

**Will it write the code if I get stuck?**
Only when you ask. A nudge points at the shape. A pointer points at existing code. The full answer is the only step where it edits the file.

**How does it decide how much to explain?**
Each concept has a level: Explore, Learning, or Familiar. A concept of this repo keeps its level in the repo's `.claude/learning-journal.md`. An Explore concept gets one portion before you write. A Learning concept gets a question only when it is worth asking. A Familiar concept gets the excerpt and no question. A chunk you wrote unassisted lowers the scaffolding. A turn that took more than a nudge brings the explanation back. A language or a tool is read from `~/.claude/pair-notes.md`, one append-only log for you across every repo.

**Will it quiz me?**
No self-rating menu, no quiz, no difficulty menu. A test run comes with no prediction. "I get it" ends new portions and writes the journal, and it does not ask what next.

**Can I stop?**
Say "stop pairing". Those exact words are the only way out. They drop the controls for the rest of the task. "I get it", "we're done", and "normal mode" leave this session owning the turn. While it owns the turn, an explanation phrase gets no offer and the stepper reminder stays quiet.

**Do I have to install the hook?**
No. The hook keeps the latch across later messages, injects the pair order on each prompt and after compaction, and offers once to stay on a subject when you say "I don't understand". From this skill's directory: `python3 turn.py hooks install claude`. There is no Cursor turn hook. A machine that installed the Claude hook from `understand` runs `python3 turn.py hooks uninstall claude` from the `understand` directory before updating, then the install above. Already updated: the install alone replaces the old command. A session that `understand` already owns stays owned under `pair`.

## It's working if

- The opening line names building or the portion loop.
- You confirmed the numbered plan before the first chunk.
- Before each question, you saw the excerpt that question uses, with its `file:line`.
- You wrote each chunk. The agent edited a file only after you asked for the full answer.
- A portion turn starts with its layer: Ticket, Rows, Code, Theory, or Decision. A building turn has none.
- The turn stays owned until you say "stop pairing".
