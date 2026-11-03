---
name: stepper
description: >-
  Track one ordered list of work and stick to the active item. Use when a
  concrete list of remaining work should be tracked, when a Stepper reminder
  is in context, when the user asks what is left, or when the user says to
  drop or replace the list. Change list state only through the stepper CLI.
compatibility: Requires Python 3
metadata:
  author: ian.handley
---

# Stepper

A session may hold several contexts. Each context is one ordered list with one active item. The CLI in this directory is the source of truth. Leave files in the home store untouched; report the CLI error. Record evidence only for a criterion you have actually established, and pass that sentence to `verify`.

**Reminder.** The one sentence a hook shows for the active item. A stop hook ends that sentence with "Add nothing." A turn whose new input is that sentence adds nothing.

**Brief.** The four-part account spoken when an item becomes active, and again when the user moves to start something else: what is done, what is left, what is blocked, and where this item sits.

**Stick.** Work the active item until it is verified, or until the user chooses hold or skip.

**Hold.** The active item is blocked. Recommend waiting, and say why.

**Skip.** The user chooses to move to the next item whose dependencies are already met.

## Session

Run `python3 <this-skill>/stepper.py` from any directory. Pass `--session`, `--root`, and `--context` on every command that changes state. Copy `--session` and `--root` from a hook message that starts with `Stepper session:`. That line names the checkout the hook registered. `--root` is that checkout. It is not where the list is stored. The list is stored in the home store, `~/.stepper`. A checkout that still has its own `.stepper` directory is moved there on the first command or hook. Leave a leftover file in the checkout; the CLI reports it and does not read or write it again. `--context` is the list's name. The session key looks like `cursor:<conversation_id>` or `claude:<session_id>`. Do not construct a key from a transcript path, filename, or any other UUID. Do not ask the user to approve a key you constructed. If that hook message is absent, say that the hook did not provide a session key, and stop. If the CLI says the root is the stepper skill directory, pass the checkout from the hook line.

Flags for a command are `python3 <this-skill>/stepper.py <command> -h`.

Done when every state change in this turn passed `--session` and `--root` from that line, and `--context` with the name of the list.

## Brief

Read `brief` from `status`. Speak all four parts: `done`, `left`, `blocked`, and `position`. An empty list is the part with nothing in it. `position` `none` means no item is held.

Do this when an item becomes active, and again before any new start. "Brief before any new start" in a session reminder names that later start. A stop reminder does not ask for a brief. Receiving either reminder is not a new start.

Done when all four parts were spoken and match `status`.

## Which context

A state change names one context. The user's words select it when they name the sitting `pr-queue`, a pull request on that sitting, or a list name they already accepted. When a message asks for a state change and names none of those, ask once which context and wait. Do not choose the context that changed most recently. Do not choose from the checkout.

A brief spoken after a change is the `brief` on that command's result. It covers the context that changed. A state change prints only `ok` and the `brief` by default. Add `--full` to get the whole store; `--brief` is still accepted and changes nothing. `attach` takes `--session`, `--root`, and `--context` like the rest.

## Status

When the user asks for status, run `status` with no `--session`. List every open context in `contexts`. For each one, name the session in `lease.session_key`, or that nobody holds it when `lease` is null. When `contexts` is empty, say the home store has no open list.

When this session holds one of those contexts, also run `status --session <key>` and speak that context's `table`. When it holds several, name each context in `held` and speak its brief.

Done when the reply names every context in `contexts` and who holds it, speaks the `table` when this session holds one context, and speaks each brief when this session holds several.

## Stick

Work the active item. `verify` it with the evidence you established. `block` it with the reason when it is waiting on someone or something. Verifying the active item activates the next pending item.

Done when the active item is verified, or the user has chosen hold or skip.

## Hold or skip

On a blocker, `block` the active item with the reason and recommend hold. External waits (a Slack reply, a manual deploy, another person) are that reason.

`skip` only when the user asks. The CLI moves to the next item, or it refuses. On a refusal, the next item depends on the held one: keep holding. `focus` of an item whose dependencies are unmet fails the same way.

Done when the user has been told to hold and why, or `skip` has moved the active item, or `skip` refused and the brief still shows the held item.

## When the list is not in this loop

- There is a concrete list of work: [OFFER.md](references/OFFER.md). A list this session already holds does not suppress the offer.
- A list is held and the user has not accepted an order: [ORDER.md](references/ORDER.md).
- The user says to drop the list or replace it: [REPLACE.md](references/REPLACE.md).

An unrelated question or a pause leaves the list in place. Answer it. Leave the brief for a new start, a list change, or a status request. While `.claude/turn-owner.json` names this session's owner as understand or pair, that skill owns the turn. Leave the list leased and untouched. A turn that already briefed or changed the list gets no stop-hook reminder. A turn whose new input is the reminder adds nothing: no brief, and no repeated questions. The brief is spoken once.

Lease, archive, and corrupt-file failures: [proposal.md](proposal.md).
