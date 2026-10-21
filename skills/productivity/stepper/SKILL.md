---
name: stepper
description: >-
  Track a short list of outstanding commitments so they survive a long
  investigation. Use when the user says to track acceptance criteria, remaining
  issues, or what's left, or when you are about to leave listed commitments
  unresolved. Change state only through the stepper CLI.
compatibility: Requires Python 3
metadata:
  author: ian.handley
---

# Stepper

Stepper keeps one small list of outstanding commitments. The CLI in this directory is the source of truth. Do not create, edit, or delete files under `.stepper/`.

Run `python3 <this-skill>/stepper.py` from any directory. Pass `--session` and `--root` on every command that changes state. Copy both from a hook message that starts with `Stepper session:`. That line names the project root the hook registered. The session key looks like `cursor:<conversation_id>` or `claude:<session_id>`. Do not construct a key from a transcript path, filename, or any other UUID. Do not ask the user to approve a key you constructed. If that hook message is absent, say that the hook did not provide a session key, and stop. If the CLI says the root contains `stepper.py`, the command was aimed at this skill's repository. Pass the project root from the hook line.

## Capture

When the user asks you to track items, register nothing yourself. Use the session key and:

```text
python3 stepper.py capture --session <key> --root <root> --item "AC-3: reset email is sent"
```

Repeat `--item` for each commitment. An id such as `AC-3` is kept. Otherwise the CLI assigns `item-1`, `item-2`, and so on. The first item becomes active. Capture fails if this session already holds a context. Without `--context` the new list takes `default`, or `default-2`, `default-3` and so on when earlier ones are still open, so another session's list is never touched. An explicit `--context <id>` that is still open fails and the error says who holds it. A closed context with the id you get is moved to `.stepper/archive/` and the new list takes the id. Do not pick a new id to get around a corrupt file. Report the CLI error.

A hook may tell you `Stepper candidate <hash>: N items`. Ask the user once whether to track them. On yes:

```text
python3 stepper.py capture --session <key> --root <root> --suggestion <hash>
```

On no: `python3 stepper.py decline --session <key> --root <root> <hash>`. Do not capture a declined or unconfirmed candidate.

## Work the list

`status` prints the active item and what is still outstanding. Use it before you decide the tracked work is finished.

```text
python3 stepper.py status --session <key> --root <root>
python3 stepper.py focus --session <key> --root <root> AC-4
python3 stepper.py verify --session <key> --root <root> AC-3 --evidence "reset mail arrived"
python3 stepper.py block --session <key> --root <root> AC-3 --reason "waiting on the provider"
python3 stepper.py unblock --session <key> --root <root> AC-3
python3 stepper.py defer --session <key> --root <root> AC-4
python3 stepper.py cancel --session <key> --root <root> AC-4
python3 stepper.py add --session <key> --root <root> --item "AC-5: lockout message"
python3 stepper.py add --session <key> --root <root> --parent AC-3 --item "AC-3b: check the reset token"
python3 stepper.py status --session <key> --root <root> --tree
python3 stepper.py pause --session <key> --root <root>
python3 stepper.py resume --session <key> --root <root>
python3 stepper.py close --session <key> --root <root>
```

`verify` checks that `--evidence` is non-empty after trimming. It does not run tests or decide whether the sentence is true. Pass evidence only for a criterion you have actually established. A false sentence would be stored.

`block` applies to the active item. `unblock` returns a blocked item to pending. `focus` is the only way to make an item active. Verifying the active item activates the next pending item and the CLI prints the reminder. Deferred and cancelled items are not verified. Close ends tracking without verifying leftover items.

`add --parent` records sub-steps under that item and does not change the active item. Keep ids the user supplied, such as `AC-3b` and `AC-3b-1`. Use `status` for top-level progress and the active path. Use `status --tree` for the full hierarchy, including what remains under one item. Do not verify a parent until the CLI accepts it. Finishing its children does not verify the parent. Do not invent child items from a description.

Only the session that holds the lease can change that context. Another session must not attach. `attach --session <key> --root <root> <context> --take` is allowed only after the user explicitly asks to continue that tracked work in this session. A new conversation does not inherit a lease.

## Reminders

Obey a `Stepper:` reminder. Do not conclude the tracked work while `status` still shows an active, pending, or blocked item. An unrelated question or a paused context is not a request to abandon the list. Answer it, and leave the list in place. While `.claude/turn-owner.json` names this session's owner as understand or pair, that skill owns the turn. Leave the list leased and untouched, and do not steer back to it.

Hooks may ask you to offer a candidate. That request is not permission to capture.
