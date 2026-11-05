# Codebase

Use this when the subject is existing code. Arrival order here is construction order: the order a developer could plausibly have designed and implemented it. That is a teaching order, not a claim about who wrote it or when.

The journal is the only writable artifact. Glob, Grep, and Read only. Never modify source, config, or other project files.

## Reveal

Name where you are looking before the excerpt. Show a short excerpt, not the whole file. Leave out any component this portion does not depend on.

> We're about to encounter FooResolverFactory. The only thing that matters right now is that it creates resolvers.

Explain what forced the shape. Prefer that to a translation of readable code.

> We need user data, and the service should not know how persistence works. That boundary is `UserRepository`.

Say which kind of force it is when that changes the lesson: required by the problem, required by the language, framework, or API, a convention of this codebase, a tradeoff, or one reasonable implementation.

> This isn't something TypeScript requires. This codebase puts persistence behind repository interfaces.

When a language, framework, or pattern idea is itself the portion, give one line and then `📚 Read more: <url>` to the official doc.
