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

One ordered list. One active item. The CLI in this directory is the source of truth. Leave files under `.stepper/` untouched; report the CLI error. Record evidence only for a criterion you have actually established, and pass that sentence to `verify`.

**Brief.** The status spoken when an item becomes active, and again when the user moves to start something else: what is done, what is left, what is blocked, and where this item sits.

**Stick.** Work the active item until it is verified, or until the user chooses hold or skip.

**Hold.** The active item is blocked. Recommend waiting, and say why.

**Skip.** The user chooses to move to the next item whose dependencies are already met.

## Session

Run `python3 <this-skill>/stepper.py` from any directory. Pass `--session` and `--root` on every command that changes state. Copy both from a hook message that starts with `Stepper session:`. That line names the project root the hook registered. The session key looks like `cursor:<conversation_id>` or `claude:<session_id>`. Do not construct a key from a transcript path, filename, or any other UUID. Do not ask the user to approve a key you constructed. If that hook message is absent, say that the hook did not provide a session key, and stop. If the CLI says the root contains `stepper.py`, pass the project root from the hook line.

Flags for a command are `python3 <this-skill>/stepper.py <command> -h`.

Done when every state change in this turn passed `--session` and `--root` from that line.

## Brief

Read `brief` from `status`. Speak all four parts: `done`, `left`, `blocked`, and `position`. An empty list is the part with nothing in it. `position` `none` means no item is held.

Do this when an item becomes active, and again before any new start.

Done when all four parts were spoken and match `status`.

## Stick

Work the active item. `verify` it with the evidence you established. `block` it with the reason when it is waiting on someone or something. Verifying the active item activates the next pending item.

Done when the active item is verified, or the user has chosen hold or skip.

## Hold or skip

On a blocker, `block` the active item with the reason and recommend hold. External waits (a Slack reply, a manual deploy, another person) are that reason.

`skip` only when the user asks. The CLI moves to the next item, or it refuses. On a refusal, the next item depends on the held one: keep holding. `focus` of an item whose dependencies are unmet fails the same way.

Done when the user has been told to hold and why, or `skip` has moved the active item, or `skip` refused and the brief still shows the held item.

## When the list is not in this loop

- No list is held, and there is a concrete list of work: [OFFER.md](references/OFFER.md).
- A list is held and the user has not accepted an order: [ORDER.md](references/ORDER.md).
- The user says to drop the list or replace it: [REPLACE.md](references/REPLACE.md).

An unrelated question or a pause leaves the list in place. Answer it, then brief. While `.claude/turn-owner.json` names this session's owner as understand or pair, that skill owns the turn. Leave the list leased and untouched.

Lease, archive, and corrupt-file failures: [proposal.md](proposal.md).
