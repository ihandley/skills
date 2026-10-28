#!/usr/bin/env python3
"""Turn-owner latch for understand and pair.

The file `.claude/turn-owner.json` records who owns the turn for one session.
Stepper reads it and stays quiet. This script writes it from Claude and Cursor
hooks. Claude UserPromptSubmit and SessionStart can inject a standing order.
Cursor beforeSubmitPrompt can record the latch and cannot inject model context.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hooks_host  # noqa: E402

OWNERS = ("understand", "pair")

UNDERSTAND_CMD = re.compile(
    r"(?:^|\s)/understand\b|<command-name>/understand</command-name>",
    re.IGNORECASE,
)
PAIR_CMD = re.compile(
    r"(?:^|\s)/pair\b|<command-name>/pair</command-name>",
    re.IGNORECASE,
)
EXPLAIN = re.compile(
    r"\bdon't understand\b|\bdo not understand\b|\bexplain\b|"
    r"\bwhat do you mean\b|\bi'm confused\b|\bi am confused\b|"
    r"\bhelp me understand\b|\bwalk me through\b",
    re.IGNORECASE,
)
RELEASE = re.compile(
    r"\bback to the task\b|\bback to the bookmark\b|\bi get it\b|"
    r"\bi've got it\b|\bive got it\b|\bi understand now\b|"
    r"\bdrop understand\b|\bnormal mode\b|\bdone understanding\b",
    re.IGNORECASE,
)
STOP_PAIR = re.compile(r"\bstop pairing\b", re.IGNORECASE)
YES = re.compile(
    r"^(?:yes|yeah|yep|stay|stay on this|go deeper|let's stay|lets stay)\b",
    re.IGNORECASE,
)

SKILL = Path(__file__).resolve().parent / "SKILL.md"


def home() -> Path:
    override = os.environ.get("UNDERSTAND_HOME")
    return Path(override).expanduser() if override else Path.home()


def latch_path(root: Path) -> Path:
    return root / ".claude" / "turn-owner.json"


def load_state(root: Path) -> dict:
    path = latch_path(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(root: Path, session_key: str, owner: str, pending: bool) -> None:
    path = latch_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "session_key": session_key,
        "owner": owner,
        "pending_offer": pending,
    }
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def hook_root(payload: dict) -> Path | None:
    roots = payload.get("workspace_roots") or []
    if roots:
        return Path(str(roots[0])).expanduser().resolve()
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        return Path(cwd).expanduser().resolve()
    return None


def session_key_from(payload: dict, platform: str) -> str | None:
    if platform == "cursor":
        ident = payload.get("conversation_id") or payload.get("session_id")
        return f"cursor:{ident}" if ident else None
    ident = payload.get("session_id")
    return f"claude:{ident}" if ident else None


def standing_order() -> str:
    return (
        "Turn owner: understand. The subject is the thread. "
        "First line of the reply: Understand · <Layer>, one of Ticket, Rows, Code, Theory, Decision. "
        "Stay on that layer. Parked work stays parked. The learning journal is the only write. "
        f"Follow {SKILL}."
    )


def offer_order() -> str:
    return (
        "The user may want to stay on this until it makes sense. "
        "Ask once: stay on this until it makes sense, or answer in place? "
        "Do not enter understand until they say yes."
    )


def in_place_order() -> str:
    return (
        "Answer in place. When the reply uses more than one of Ticket, Rows, Code, Theory, or Decision, "
        "label each block. Leave the turn owner empty."
    )


def pair_order() -> str:
    return (
        "Turn owner: pair. This session owns the turn until the user says stop pairing. "
        "The understand offer stays quiet."
    )


def emit_context(platform: str, event: str, text: str | None) -> dict | None:
    if not text:
        return None
    if platform == "cursor":
        if event == "sessionStart":
            return {"additional_context": text}
        return None
    if event in ("UserPromptSubmit", "SessionStart"):
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": text,
            }
        }
    return None


def current(state: dict, key: str) -> tuple[str, bool]:
    if state.get("session_key") != key:
        return "", False
    owner = state.get("owner") or ""
    if owner not in OWNERS:
        owner = ""
    return owner, bool(state.get("pending_offer"))


def decide(owner: str, pending: bool, prompt: str) -> tuple[str, bool, str | None]:
    """Return the next owner, pending flag, and text to inject."""
    if UNDERSTAND_CMD.search(prompt):
        return "understand", False, standing_order()
    if PAIR_CMD.search(prompt):
        return "pair", False, pair_order()
    if owner == "understand" and RELEASE.search(prompt):
        return "", False, None
    if owner == "pair" and STOP_PAIR.search(prompt):
        return "", False, None
    if owner == "pair":
        return "pair", False, None
    if owner == "understand":
        return "understand", False, standing_order()
    if pending and YES.search(prompt.strip()):
        return "understand", False, standing_order()
    if pending:
        return "", False, in_place_order()
    if EXPLAIN.search(prompt):
        return "", True, offer_order()
    return owner, pending, None


def handle_hook(root: Path, platform: str, payload: dict) -> dict | None:
    event = payload.get("hook_event_name") or ""
    key = session_key_from(payload, platform)
    if not key:
        return None
    prompt_event = event in ("UserPromptSubmit", "beforeSubmitPrompt")
    session_event = event in ("SessionStart", "sessionStart")
    if not prompt_event and not session_event:
        return None
    state = load_state(root)
    owner, pending = current(state, key)
    if session_event:
        if owner == "understand":
            return emit_context(platform, event, standing_order())
        if owner == "pair":
            return emit_context(platform, event, pair_order())
        return None
    next_owner, next_pending, text = decide(owner, pending, payload.get("prompt") or "")
    if next_owner != owner or next_pending != pending or state.get("session_key") != key:
        if next_owner or next_pending or state.get("session_key") == key:
            save_state(root, key, next_owner, next_pending)
    return emit_context(platform, event, text)


def hook_spec() -> hooks_host.Spec:
    return hooks_host.Spec(
        tag="turn-owner",
        state_dir=home() / ".understand",
        script=Path(__file__).resolve(),
        events={
            "cursor": [hooks_host.Event(name) for name in ("sessionStart", "beforeSubmitPrompt")],
            "claude": [
                hooks_host.Event("SessionStart", matcher="startup|resume|compact"),
                hooks_host.Event("UserPromptSubmit"),
            ],
        },
    )


def install_hooks(platform: str) -> dict:
    return hooks_host.install(hook_spec(), home(), platform)


def uninstall_hooks(platform: str) -> dict:
    return hooks_host.uninstall(hook_spec(), home(), platform)


def hooks_status() -> dict:
    return hooks_host.status(hook_spec(), home())


def emit(data: dict, code: int = 0) -> int:
    sys.stdout.write(json.dumps(data, indent=2) + "\n")
    return code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="turn.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    hook = sub.add_parser("hook")
    hook.add_argument("--platform", required=True, choices=("claude", "cursor"))
    hook.add_argument("--tag", default="turn-owner")
    hooks = sub.add_parser("hooks")
    hooks_sub = hooks.add_subparsers(dest="hooks_cmd", required=True)
    for name in ("install", "uninstall"):
        command = hooks_sub.add_parser(name)
        command.add_argument("platform", choices=("claude", "cursor"))
    hooks_sub.add_parser("status")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "hook":
            raw = sys.stdin.read()
            try:
                payload = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                return 0
            if not isinstance(payload, dict):
                return 0
            root = hook_root(payload)
            if root is None:
                return 0
            output = handle_hook(root, args.platform, payload)
            if output:
                sys.stdout.write(json.dumps(output) + "\n")
            return 0
        if args.hooks_cmd == "install":
            return emit(install_hooks(args.platform))
        if args.hooks_cmd == "uninstall":
            return emit(uninstall_hooks(args.platform))
        return emit(hooks_status())
    except (OSError, json.JSONDecodeError, ValueError, hooks_host.HostError) as exc:
        return emit({"ok": False, "error": str(exc)}, 1)


if __name__ == "__main__":
    sys.exit(main())
