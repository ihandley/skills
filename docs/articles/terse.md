# Terse: Stop Making People Read Your AI Slop

*An opinionated writing skill for engineers who want to say more with fewer words.*

AI can turn a two-sentence Slack message into a three-paragraph email in seconds.

It adds a friendly introduction, explains the context everyone already knows, carefully balances every assertion, and closes with an offer to help. The actual message is still in there. Someone just has to find it.

Generating all those words costs almost nothing. Reading them takes time.

That's the problem [Terse](../../skills/productivity/terse/SKILL.md) is designed to solve.

Terse is an open-source agent skill that drafts and rewrites workplace communication for Slack, email, Jira, Confluence, and pull requests. Its objective is simple: minimize length and maximize signal.

But shorter writing isn't necessarily better writing. Remove the wrong sentence and you lose the context. Cut a qualifier and a suspicion becomes a fact. Eliminate too much explanation and the reader has to reconstruct your reasoning.

Terse has rules for deciding what stays.

## The cost of being concise

Consider this Slack message:

> Hi team! I wanted to provide a quick update regarding the deployment issue we encountered earlier today. After investigating, it looks like the service may be experiencing connectivity problems related to Redis. Would someone be able to take a look when they have a chance? Thanks so much!

A shorter version would be:

> The service may be losing its Redis connection. Could you check the connection logs?

The greeting, announcement, and vague invitation are gone. The suspected problem remains uncertain, and the request names an action someone can complete.

There's an important limitation here. Terse can only make that specific request if checking the logs is supported by the author's instructions or source material. Otherwise, it must preserve the original, less specific request or ask for clarification.

That constraint matters because language models are remarkably willing to invent missing details when doing so makes a sentence sound more useful.

Terse doesn't get to do that.

It preserves facts, uncertainty, commitments, technical identifiers, and the force of a request. It removes optional information before shortening anything the reader actually needs.

## Write in the order people understand

Suppose you receive this message:

> The retry failed because the connection pool was exhausted.

If you know about the retry, that's enough. If you don't, you have to work backward to understand what happened.

Terse makes reading order an explicit part of writing.

When a result introduces something unfamiliar, it begins with one sentence of context:

> We retried the database migration. The retry failed because the connection pool was exhausted.

When the reader already knows the situation, Terse leads with the result instead.

This isn't a rule about always putting context first. It's a rule about what the reader needs to know before the next sentence makes sense.

The same principle applies to identifiers. An error string, address, or long resource ID may be essential, but repeating it throughout a message makes the text harder to follow.

Terse keeps those details intact and places them where the reader needs them. Multiple identifiers can move into a labeled block instead of interrupting the explanation.

The goal is to reduce the number of times someone has to reread a sentence.

## Give people something they can finish

AI assistants have a peculiar habit of turning requests into opportunities to decline.

> I was wondering if you might have a chance to review this when you have some availability.

Nobody has been told what needs to happen or when the work is done.

Compare that with:

> Could you review the retry logic and approve the PR if it looks correct?

The second request describes a finishable action.

Terse requires that kind of request at the end of the prose, after the reader has the context necessary to act.

That choice is deliberately rigid. It prevents an important request from getting buried between background information and a cheerful closing.

It also creates a tradeoff. Some conversations genuinely call for an open question, a softer invitation, or a discussion rather than a task. Terse is optimized for communication that needs a concrete next action, and its direct-request rule won't fit every situation.

The skill favors action over conversational ambiguity.

## Keep the human. Lose the chatbot.

Here's something AI might write in a pull-request review:

> Fantastic work! This is an excellent approach that significantly enhances the robustness and maintainability of our authentication infrastructure.

It sounds supportive. It also contains almost no useful information.

A more helpful response might be:

> Approved. The change removes the duplicate authentication path.

Now the reader knows the decision and the reason.

Terse has a specific rule about this: gratitude is allowed, but praise is removed.

"Thanks for fixing the deployment" acknowledges an action. "Amazing work on the deployment!" evaluates the work.

The distinction is intentional. An assistant shouldn't invent approval or enthusiasm the author never expressed.

The same applies to disagreement.

If the original says:

> This makes no sense. We're adding another abstraction without removing any complexity.

Terse doesn't automatically turn it into:

> While I appreciate the thoughtful approach, there may be opportunities to simplify the implementation.

It preserves the criticism. It only softens language when it attacks someone, claims to know their motives, or gets in the way of the request.

The shipped voice is direct, conversational, and candid. A personal voice file can override its stylistic defaults, including word choice, contractions, humor, and opinions.

The point is to preserve the person doing the writing.

## One size doesn't fit every message

A Slack message and a Jira issue have different obligations.

A coworker reading Slack probably knows what happened this morning. Someone opening a Jira ticket three months later may know nothing about it.

Terse uses separate modes because the right amount of context depends on where the writing will live.

For Slack, it favors short paragraphs, natural contractions, and a little caution around unverified diagnoses.

For Jira, it preserves the problem, expected behavior, evidence, constraints, and acceptance criteria when the source provides them.

For Confluence, it records decisions and their consequences without repeating information already available in linked documents.

Pull-request descriptions have an especially opinionated structure.

Rather than listing modified files or paraphrasing the commit history, Terse focuses on what a reviewer needs to understand before merging. When the change involves an important flow or boundary, it can use a small diagram, call tree, or diff to show the shape of the change.

Before-and-after evidence is included only when it exists. Merge risks are identified only when they're supported by the source.

The prose is normally kept under fifteen lines, with room for required visuals.

A reviewer should be able to understand why the change exists without having to read an essay about how every line was written.

## The problem with AI writing tells

Even after shortening a message, AI leaves recognizable fingerprints.

It loves phrases like "at its core" and "it's not just X, it's Y." It announces that something is important instead of explaining why. It adds conclusions that restate what the reader just finished reading.

Terse runs a separate editing pass against these patterns.

It looks for inflated claims, needless signposting, promotional language, repetitive sentence structures, and generic endings.

It doesn't blindly ban individual words. "Robust" is useful when describing fault tolerance. It's meaningless when used as generic praise for an implementation.

Some preferences are less nuanced.

Terse bans em dashes and en dashes entirely. It also prohibits mid-sentence parentheses.

Those aren't universal writing rules. They're deliberate style choices.

The dash restriction is enforced by a bundled Python script, so compliance doesn't depend entirely on whether the model remembers the instruction.

It's a small example of something useful in agent design: when a requirement can be checked mechanically, don't rely exclusively on prompting.

## How to use Terse

Terse lives in my [GitHub skills repository](https://github.com/ihandley/skills/tree/main/skills/productivity/terse).

For Claude Code, install the plugin:

```bash
claude plugin marketplace add ihandley/skills
claude plugin install ihandley-skills@ihandley
```

For Cursor, Codex, or other supported agents, install it with:

```bash
npx skills@latest add ihandley/skills
```

You can invoke `/terse` directly or let the agent select it when you're drafting or rewriting workplace communication.

Its rules apply only to the outward-facing draft. They don't control your conversation with the agent, and they stop once the draft is delivered.

Terse is intentionally narrower than a general-purpose writing skill. It isn't meant for compressing existing documentation, editing source code, or helping someone develop a long-form essay. Those are different jobs with different requirements.

## Who pays for the words?

When you write a message yourself, its length costs you time. You have an incentive to finish.

With AI, that constraint largely disappears. You can generate several paragraphs as easily as one sentence.

But nothing changed for the person reading them.

They still have to identify the important information, separate facts from speculation, understand what you're asking, and decide what to do next.

Terse moves some of that work back to the author.

The next time an assistant drafts a Slack message, it should already have figured out what the reader needs to know, what can be omitted, and what action the message is asking for.

The reader shouldn't have to do that editing for you.
