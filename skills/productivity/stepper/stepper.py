#!/usr/bin/env python3
"""Deterministic working memory for a short list of outstanding commitments.

The CLI is the only writer of tracking state. Hooks call `hook` and do not
duplicate transition rules.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

VERSION = 1
MAX_DEPTH = 2
STATUSES = ("pending", "active", "blocked", "verified", "deferred", "cancelled")
OUTSTANDING = ("pending", "active", "blocked")
LEGAL = {
    "pending": {"active", "verified", "deferred", "cancelled"},
    "active": {"pending", "blocked", "verified", "deferred", "cancelled"},
    "blocked": {"pending", "active", "deferred", "cancelled"},
    "deferred": {"active", "cancelled"},
    "verified": set(),
    "cancelled": set(),
}
CONTEXT_KEYS = {
    "version",
    "id",
    "created_at",
    "updated_at",
    "closed",
    "paused",
    "lease",
    "source_hash",
    "next_seq",
    "items",
}
ITEM_KEYS = {
    "id",
    "description",
    "completion_criteria",
    "status",
    "evidence",
    "blocked_reason",
    "order",
    "parent_id",
}
SESSION_KEYS = {
    "version",
    "session_key",
    "platform",
    "prompt_class",
    "generation_id",
    "compaction_pending",
    "announce_key",
    "last_assistant_text",
    "candidate",
    "candidate_generation",
    "parked",
    "reminded_generation",
    "followup_generation",
}
CURSOR_EVENTS = {
    "sessionStart",
    "sessionEnd",
    "beforeSubmitPrompt",
    "afterAgentResponse",
    "postToolUse",
    "stop",
    "preCompact",
}
CLAUDE_EVENTS = {
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "PostToolUse",
    "Stop",
    "PreCompact",
}
HEADING = re.compile(
    r"(?i)\b(acceptance criteria|outstanding|remaining work|unresolved findings|"
    r"to-?dos?|still open|not yet (?:met|done|satisfied))\b"
)
CHECKED = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[[xX]\]\s+")
OPEN_BOX = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[\s\]\s+(.+?)\s*$")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+?)\s*$")
ITEM_ID = re.compile(r"^([A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+)\s*[:\-]\s+(.+)$")
BARE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)+$")
STATUS_WORD = re.compile(
    r"(?i)\b(outstanding|not met|unmet|failed|remaining|unresolved|todo)\b"
)
STEPPER_PROMPT = re.compile(
    r"(?i)\b(stepper|track (?:these|those|this|what)|keep track|what'?s left|"
    r"where are we|what'?s next|stop tracking|pause stepper|resume stepper)\b"
)
QUESTION = re.compile(
    r"(?i)^(how|why|what|when|who|where|can you explain|explain)\b"
)
CONTEXT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


class StepperError(Exception):
    pass


class CorruptError(StepperError):
    def __init__(self, path: Path, quarantine: Path | None, detail: str):
        self.path = path
        self.quarantine = quarantine
        loc = f" Quarantine copy: {quarantine}." if quarantine else ""
        super().__init__(
            f"corrupt state at {path}: {detail}.{loc} "
            "The original file was left in place. No replacement context was created."
        )


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def home() -> Path:
    override = os.environ.get("STEPPER_HOME")
    return Path(override).expanduser() if override else Path.home()


def resolve_root(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser().resolve()
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def store(root: Path) -> Path:
    return root / ".stepper"


def ensure_store(root: Path) -> Path:
    base = store(root)
    for name in ("contexts", "sessions", "quarantine"):
        (base / name).mkdir(parents=True, exist_ok=True)
    _exclude(root)
    return base


def _exclude(root: Path) -> None:
    try:
        out = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--git-path", "info/exclude"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return
    path = Path(out)
    if not path.is_absolute():
        path = (root / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else ""
    lines = text.splitlines()
    if ".stepper/" in lines:
        return
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + ".stepper/\n")


@contextmanager
def locked(root: Path, block: bool = True):
    base = ensure_store(root)
    fd = os.open(base / ".lock", os.O_CREAT | os.O_RDWR, 0o644)
    flag = fcntl.LOCK_EX if block else fcntl.LOCK_EX | fcntl.LOCK_NB
    try:
        try:
            fcntl.flock(fd, flag)
        except BlockingIOError as exc:
            raise StepperError("state is locked by another stepper process") from exc
        yield base
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def write_json(path: Path, data: dict) -> None:
    atomic_write(path, json.dumps(data, indent=2) + "\n")


def quarantine(root: Path, path: Path) -> Path | None:
    try:
        original = path.read_bytes()
    except OSError:
        return None
    dest = store(root) / "quarantine" / f"{path.name}-{stamp()}"
    tmp = dest.with_name(dest.name + ".tmp")
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(original)
        os.replace(tmp, dest)
    except OSError:
        tmp.unlink(missing_ok=True)
        return None
    try:
        if path.read_bytes() != original:
            raise StepperError(f"original changed while copying {path}")
    except OSError as exc:
        raise StepperError(f"could not re-read {path}") from exc
    return dest


def _fail_corrupt(root: Path, path: Path, detail: str) -> None:
    copy = quarantine(root, path)
    raise CorruptError(path, copy, detail)


def load_json(root: Path, path: Path) -> dict:
    try:
        raw = path.read_text()
    except OSError as exc:
        raise StepperError(f"could not read {path}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fail_corrupt(root, path, "invalid JSON")
        raise exc
    if not isinstance(data, dict):
        _fail_corrupt(root, path, "expected an object")
    return data


def session_path(root: Path, key: str) -> Path:
    platform, _, sid = key.partition(":")
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", sid)
    return store(root) / "sessions" / f"{platform}_{safe}.json"


def context_path(root: Path, context_id: str) -> Path:
    if not CONTEXT_ID.fullmatch(context_id):
        raise StepperError(f"invalid context id {context_id!r}")
    return store(root) / "contexts" / f"{context_id}.json"


def fresh_session(key: str, platform: str) -> dict:
    return {
        "version": VERSION,
        "session_key": key,
        "platform": platform,
        "prompt_class": "unrelated",
        "generation_id": None,
        "compaction_pending": False,
        "announce_key": False,
        "last_assistant_text": "",
        "candidate": None,
        "candidate_generation": None,
        "parked": None,
        "reminded_generation": None,
        "followup_generation": None,
    }


def validate_session(data: dict) -> None:
    if set(data) != SESSION_KEYS or data.get("version") != VERSION:
        raise ValueError("session schema")
    if not isinstance(data["session_key"], str) or ":" not in data["session_key"]:
        raise ValueError("session key")


def load_session(root: Path, key: str) -> dict | None:
    path = session_path(root, key)
    if not path.exists():
        return None
    data = load_json(root, path)
    try:
        validate_session(data)
    except ValueError as exc:
        _fail_corrupt(root, path, str(exc))
    return data


def save_session(root: Path, data: dict) -> None:
    write_json(session_path(root, data["session_key"]), data)


def require_session(root: Path, key: str) -> dict:
    data = load_session(root, key)
    if data is None:
        raise StepperError(
            f"unknown session {key}. A hook registers the session before commands can change state."
        )
    return data


def blank_item(item_id: str, description: str, criteria: str, order: int) -> dict:
    return {
        "id": item_id,
        "description": description,
        "completion_criteria": criteria,
        "status": "pending",
        "evidence": None,
        "blocked_reason": None,
        "order": order,
        "parent_id": None,
    }


def validate_context(data: dict) -> None:
    if set(data) != CONTEXT_KEYS or data.get("version") != VERSION:
        raise ValueError("context schema")
    if not CONTEXT_ID.fullmatch(data.get("id") or ""):
        raise ValueError("context id")
    if not isinstance(data["closed"], bool) or not isinstance(data["paused"], bool):
        raise ValueError("flags")
    if data["closed"] and data["lease"] is not None:
        raise ValueError("closed context still leased")
    lease = data["lease"]
    if lease is not None:
        if not isinstance(lease, dict) or set(lease) != {"session_key", "acquired_at"}:
            raise ValueError("lease")
        if not isinstance(lease["session_key"], str):
            raise ValueError("lease session")
    if not isinstance(data["items"], list) or not isinstance(data["next_seq"], int):
        raise ValueError("items")
    seen = set()
    active = 0
    for item in data["items"]:
        if not isinstance(item, dict) or set(item) - {"parent_id"} != ITEM_KEYS - {"parent_id"}:
            raise ValueError("item schema")
        if "parent_id" in item and item["parent_id"] is not None and not isinstance(item["parent_id"], str):
            raise ValueError("parent")
        if item["status"] not in STATUSES:
            raise ValueError("status")
        if item["id"] in seen or not isinstance(item["id"], str):
            raise ValueError("item id")
        seen.add(item["id"])
        if item["status"] == "active":
            active += 1
        if item["evidence"] is not None and not isinstance(item["evidence"], str):
            raise ValueError("evidence")
        if item["status"] == "verified" and not (item["evidence"] or "").strip():
            raise ValueError("verified without evidence")
        if not isinstance(item["order"], int):
            raise ValueError("order")
    if active > 1:
        raise ValueError("multiple active items")
    ids = {item["id"] for item in data["items"]}
    for item in data["items"]:
        parent = item.get("parent_id")
        seen = set()
        while parent is not None:
            if parent not in ids or parent in seen or parent == item["id"]:
                raise ValueError("parent")
            seen.add(parent)
            parent = next(
                candidate.get("parent_id")
                for candidate in data["items"]
                if candidate["id"] == parent
            )


def normalize_context(data: dict) -> dict:
    for item in data["items"]:
        item["parent_id"] = item.get("parent_id")
    return data


def load_context(root: Path, context_id: str) -> dict:
    path = context_path(root, context_id)
    if not path.exists():
        raise StepperError(f"no context {context_id}")
    data = load_json(root, path)
    try:
        validate_context(data)
    except ValueError as exc:
        _fail_corrupt(root, path, str(exc))
    return normalize_context(data)


def save_context(root: Path, data: dict) -> None:
    validate_context(data)
    data["updated_at"] = now()
    write_json(context_path(root, data["id"]), data)


def iter_context_files(root: Path) -> list[Path]:
    folder = store(root) / "contexts"
    if not folder.exists():
        return []
    return sorted(p for p in folder.glob("*.json") if p.is_file())


def read_contexts(root: Path) -> tuple[list[dict], list[str]]:
    good = []
    bad = []
    for path in iter_context_files(root):
        try:
            data = load_json(root, path)
            validate_context(data)
        except CorruptError as exc:
            bad.append(str(exc.path))
            continue
        except (StepperError, ValueError):
            copy = quarantine(root, path)
            bad.append(str(path if copy is None else path))
            continue
        good.append(normalize_context(data))
    return good, bad


def leased_by(root: Path, session_key: str) -> dict | None:
    contexts, _bad = read_contexts(root)
    for ctx in contexts:
        lease = ctx["lease"]
        if lease and lease["session_key"] == session_key and not ctx["closed"]:
            return ctx
    return None


def suggestions_path(root: Path) -> Path:
    return store(root) / "suggestions.json"


def load_suggestions(root: Path) -> dict:
    path = suggestions_path(root)
    if not path.exists():
        return {"version": VERSION, "items": {}}
    data = load_json(root, path)
    if data.get("version") != VERSION or not isinstance(data.get("items"), dict):
        _fail_corrupt(root, path, "suggestions schema")
    return data


def save_suggestions(root: Path, data: dict) -> None:
    write_json(suggestions_path(root), data)


def suggestion_status(root: Path, digest: str) -> str | None:
    return (load_suggestions(root)["items"].get(digest) or {}).get("status")


def is_complete(ctx: dict) -> bool:
    items = ctx["items"]
    if not items:
        return False
    if any(item["status"] not in ("verified", "cancelled") for item in items):
        return False
    return any(item["status"] == "verified" for item in items)


def has_outstanding(ctx: dict) -> bool:
    return any(item["status"] in OUTSTANDING for item in ctx["items"])


def reminder(ctx: dict) -> str:
    if ctx["closed"]:
        return "Stepper: tracking is closed."
    if is_complete(ctx):
        return "Stepper: tracked work is complete."
    if any(item.get("parent_id") for item in ctx["items"]):
        return _hierarchy_reminder(ctx)
    active = [item for item in ctx["items"] if item["status"] == "active"]
    pending = sorted(
        (item for item in ctx["items"] if item["status"] == "pending"),
        key=lambda item: item["order"],
    )
    blocked = [item for item in ctx["items"] if item["status"] == "blocked"]
    deferred = [item for item in ctx["items"] if item["status"] == "deferred"]
    bits = []
    if active:
        bits.append(f"{active[0]['id']} active")
    if pending:
        bits.append(", ".join(item["id"] for item in pending) + " pending")
    if blocked:
        bits.append(", ".join(item["id"] for item in blocked) + " blocked")
    if not bits and deferred:
        names = ", ".join(item["id"] for item in deferred)
        return f"Stepper: nothing actionable remains; {names} deferred."
    if not bits:
        return "Stepper: nothing outstanding."
    outstanding = active + pending + blocked
    if len(outstanding) == 1:
        tail = "until it is resolved or explicitly deferred"
    elif len(outstanding) == 2:
        tail = "until both are resolved or explicitly deferred"
    else:
        tail = "until they are resolved or explicitly deferred"
    return (
        "Stepper: "
        + "; ".join(bits)
        + f". Do not conclude the tracked work {tail}."
    )


def public_context(ctx: dict) -> dict:
    return {
        "id": ctx["id"],
        "closed": ctx["closed"],
        "paused": ctx["paused"],
        "lease": ctx["lease"],
        "source_hash": ctx["source_hash"],
        "complete": is_complete(ctx),
        "reminder": reminder(ctx),
        "items": ctx["items"],
    }


def split_label(text: str) -> tuple[str | None, str]:
    match = ITEM_ID.match(text.strip())
    if not match:
        return None, text.strip()
    return match.group(1), match.group(2).strip()


def parse_item_arg(text: str, seq: int) -> tuple[dict, int]:
    parts = [part.strip() for part in text.split("|")]
    if len(parts) == 3:
        item_id, description, criteria = parts
    elif len(parts) == 2:
        item_id, description = parts
        criteria = description
    else:
        item_id, description = split_label(text)
        criteria = description
    if not description:
        raise StepperError("an item needs a description")
    if not item_id:
        item_id = f"item-{seq}"
        seq += 1
    if not BARE_ID.fullmatch(item_id):
        raise StepperError(f"invalid item id {item_id!r}")
    return blank_item(item_id, description, criteria or description, 0), seq


def parse_candidates(text: str) -> dict | None:
    entries = []
    in_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if HEADING.search(stripped) and not LIST_ITEM.match(line):
            in_section = True
            continue
        if CHECKED.match(line):
            continue
        box = OPEN_BOX.match(line)
        if box and in_section:
            entries.append(box.group(1).strip())
            continue
        item = LIST_ITEM.match(line)
        if item and in_section:
            entries.append(item.group(1).strip())
            continue
        labeled = ITEM_ID.match(stripped)
        if labeled and (in_section or STATUS_WORD.search(stripped)):
            entries.append(stripped)
            continue
        if not LIST_ITEM.match(line) and not stripped.startswith("#"):
            in_section = HEADING.search(stripped) is not None
    if not entries:
        return None
    normalized = []
    for raw in entries:
        item_id, description = split_label(raw)
        description = " ".join(description.split())
        if not description:
            continue
        normalized.append(
            {
                "id": item_id,
                "description": description,
                "completion_criteria": description,
            }
        )
    if not normalized:
        return None
    canon = [
        {
            "id": entry["id"] or "",
            "description": entry["description"].lower(),
        }
        for entry in normalized
    ]
    digest = hashlib.sha256(
        json.dumps(canon, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()[:16]
    return {"hash": digest, "count": len(normalized), "entries": normalized}


def is_stepper_prompt(prompt: str) -> bool:
    return STEPPER_PROMPT.search(prompt or "") is not None


def is_question(prompt: str) -> bool:
    text = (prompt or "").strip()
    return "?" in text or QUESTION.match(text) is not None


def classify(prompt: str, ctx: dict | None) -> str:
    if is_stepper_prompt(prompt):
        return "stepper"
    if ctx is None:
        return "unrelated"
    if is_question(prompt):
        active = next((item["id"] for item in ctx["items"] if item["status"] == "active"), "")
        if not active or active.lower() not in prompt.lower():
            return "unrelated"
    return "tracked"


def _item(ctx: dict, item_id: str) -> dict:
    for item in ctx["items"]:
        if item["id"] == item_id:
            return item
    raise StepperError(f"no item {item_id}")


def _children(ctx: dict, parent_id: str | None) -> list[dict]:
    return sorted(
        (item for item in ctx["items"] if item.get("parent_id") == parent_id),
        key=lambda item: item["order"],
    )


def _parent(ctx: dict, item: dict) -> dict | None:
    parent_id = item.get("parent_id")
    if parent_id is None:
        return None
    return _item(ctx, parent_id)


def _ancestors(ctx: dict, item: dict) -> list[dict]:
    chain = []
    seen = set()
    current = _parent(ctx, item)
    while current is not None:
        if current["id"] in seen:
            raise StepperError(f"parent cycle at {current['id']}")
        seen.add(current["id"])
        chain.append(current)
        current = _parent(ctx, current)
    chain.reverse()
    return chain


def _descendants(ctx: dict, item: dict) -> list[dict]:
    found = []
    for child in _children(ctx, item["id"]):
        found.append(child)
        found.extend(_descendants(ctx, child))
    return found


def _depth(ctx: dict, item: dict) -> int:
    return len(_ancestors(ctx, item))


def _eligible(ctx: dict, item: dict) -> bool:
    return all(child["status"] in ("verified", "cancelled") for child in _descendants(ctx, item))


def _blocking_descendants(ctx: dict, item: dict, statuses: tuple[str, ...]) -> list[dict]:
    return [child for child in _descendants(ctx, item) if child["status"] in statuses]


def _until(ids: list[str]) -> str:
    if len(ids) == 1:
        return f"until {ids[0]} is resolved"
    return f"until {', '.join(ids)} are resolved"


def _guard_ancestors(ctx: dict, item: dict) -> None:
    for ancestor in _ancestors(ctx, item):
        if ancestor["status"] in ("verified", "cancelled"):
            raise StepperError(
                f"cannot change {item['id']} because {ancestor['id']} is {ancestor['status']}"
            )


def _select_branch(ctx: dict, node: dict) -> dict | None:
    if node["status"] != "pending":
        return None
    for child in _children(ctx, node["id"]):
        chosen = _select_branch(ctx, child)
        if chosen is not None:
            return chosen
    if not _children(ctx, node["id"]) or _eligible(ctx, node):
        return node
    if _blocking_descendants(ctx, node, ("pending", "active", "blocked", "deferred")):
        return node
    return None


def _next_hierarchical(ctx: dict, finished: dict) -> dict | None:
    for sibling in _children(ctx, finished.get("parent_id")):
        if sibling["id"] == finished["id"]:
            continue
        chosen = _select_branch(ctx, sibling)
        if chosen is not None:
            return chosen
    parent = _parent(ctx, finished)
    if parent is not None and parent["status"] == "pending" and _eligible(ctx, parent):
        return parent
    if parent is not None:
        return _next_hierarchical(ctx, parent)
    return None


def _progress(ctx: dict) -> dict:
    tops = _children(ctx, None)
    resolved = sum(1 for item in tops if item["status"] in ("verified", "cancelled"))
    active = next((item for item in ctx["items"] if item["status"] == "active"), None)
    path = []
    if active is not None:
        path = [item["id"] for item in _ancestors(ctx, active)] + [active["id"]]
    return {
        "top_level": {"resolved": resolved, "total": len(tops)},
        "active_path": path,
    }


def _tree_node(ctx: dict, item: dict) -> dict:
    children = _children(ctx, item["id"])
    resolved = sum(1 for child in children if child["status"] in ("verified", "cancelled"))
    return {
        "id": item["id"],
        "status": item["status"],
        "children_resolved": resolved,
        "children_total": len(children),
        "children": [_tree_node(ctx, child) for child in children],
    }


def _hierarchy_reminder(ctx: dict) -> str:
    progress = _progress(ctx)
    counts = progress["top_level"]
    parts = []
    if progress["active_path"]:
        parts.append(" → ".join(progress["active_path"]) + " active")
    else:
        parts.append("no active item")
    parts.append(f"top-level {counts['resolved']}/{counts['total']}")
    active = next((item for item in ctx["items"] if item["status"] == "active"), None)
    parent = _parent(ctx, active) if active is not None else None
    if parent is not None:
        children = _children(ctx, parent["id"])
        resolved = sum(1 for child in children if child["status"] in ("verified", "cancelled"))
        parts.append(f"{parent['id']} {resolved}/{len(children)}")
    return "Stepper: " + ". ".join(parts) + "."


def _demote_active(ctx: dict) -> None:
    for item in ctx["items"]:
        if item["status"] == "active":
            item["status"] = "pending"


def _activate_next(ctx: dict, finished: dict | None = None) -> None:
    if any(item.get("parent_id") for item in ctx["items"]):
        if finished is None:
            for item in _children(ctx, None):
                chosen = _select_branch(ctx, item)
                if chosen is not None:
                    chosen["status"] = "active"
                    return
            return
        chosen = _next_hierarchical(ctx, finished)
        if chosen is not None:
            chosen["status"] = "active"
        return
    pending = sorted(
        (item for item in ctx["items"] if item["status"] == "pending"),
        key=lambda item: item["order"],
    )
    if pending:
        pending[0]["status"] = "active"


def transition(
    ctx: dict,
    item_id: str,
    new_status: str,
    evidence: str | None = None,
    reason: str | None = None,
) -> None:
    if ctx["closed"]:
        raise StepperError(f"context {ctx['id']} is closed")
    item = _item(ctx, item_id)
    _guard_ancestors(ctx, item)
    if new_status == "verified":
        blocking = _blocking_descendants(ctx, item, ("pending", "active", "blocked", "deferred"))
        if blocking:
            raise StepperError(f"cannot verify {item_id} {_until([child['id'] for child in blocking])}")
    if new_status in ("deferred", "cancelled"):
        blocking = _blocking_descendants(ctx, item, ("pending", "active", "blocked"))
        if blocking:
            verb = "defer" if new_status == "deferred" else "cancel"
            raise StepperError(f"cannot {verb} {item_id} {_until([child['id'] for child in blocking])}")
    current = item["status"]
    if new_status == "verified":
        evidence = None if evidence is None else evidence.strip()
    if new_status == "blocked":
        reason = None if reason is None else reason.strip()
    if current == new_status:
        if new_status == "verified" and evidence is not None and item["evidence"] != evidence:
            raise StepperError("verified evidence is already recorded")
        if new_status == "blocked" and reason is not None and item["blocked_reason"] != reason:
            raise StepperError("blocked reason is already recorded")
        return
    if new_status not in LEGAL[current]:
        raise StepperError(f"cannot move {item_id} from {current} to {new_status}")
    was_active = current == "active"
    if new_status == "active":
        _demote_active(ctx)
        item["blocked_reason"] = None
    elif new_status == "verified":
        if not evidence:
            raise StepperError("verification evidence must be a non-empty string")
        item["evidence"] = evidence
    elif new_status == "blocked":
        if not reason:
            raise StepperError("block requires a reason")
        item["blocked_reason"] = reason
    if current == "blocked" and new_status != "blocked":
        item["blocked_reason"] = None
    item["status"] = new_status
    if was_active and new_status == "verified":
        _activate_next(ctx, item)


def require_holder(root: Path, session_key: str) -> dict:
    require_session(root, session_key)
    contexts, bad = read_contexts(root)
    for ctx in contexts:
        lease = ctx["lease"]
        if lease and lease["session_key"] == session_key and not ctx["closed"]:
            return ctx
    if bad:
        names = ", ".join(bad)
        raise StepperError(
            f"corrupt state at {names}. The original file was left in place. "
            "No replacement context was created."
        )
    raise StepperError(f"session {session_key} does not hold a context")


def result(ctx: dict, **extra) -> dict:
    body = {
        "ok": True,
        "context": public_context(ctx),
        "reminder": reminder(ctx),
        "progress": _progress(ctx),
    }
    body.update(extra)
    return body


def cmd_capture(root: Path, session_key: str, context_id: str, items: list[str], suggestion: str | None) -> dict:
    require_session(root, session_key)
    if leased_by(root, session_key) is not None:
        raise StepperError("this session already holds a context; detach or close it first")
    path = context_path(root, context_id)
    if path.exists():
        load_context(root, context_id)
        raise StepperError(f"context {context_id} already exists")
    seq = 1
    built = []
    source_hash = None
    if suggestion:
        if items:
            raise StepperError("pass either --suggestion or --item, not both")
        record = load_suggestions(root)["items"].get(suggestion)
        if not record:
            raise StepperError(f"unknown suggestion {suggestion}")
        if record["status"] == "declined":
            raise StepperError(f"suggestion {suggestion} was declined")
        if record["status"] == "accepted":
            raise StepperError(f"suggestion {suggestion} was already accepted")
        source_hash = suggestion
        for entry in record["entries"]:
            item_id = entry["id"]
            if not item_id:
                item_id = f"item-{seq}"
                seq += 1
            built.append(
                blank_item(item_id, entry["description"], entry["completion_criteria"], len(built))
            )
    else:
        if not items:
            raise StepperError("capture needs at least one --item")
        for raw in items:
            item, seq = parse_item_arg(raw, seq)
            item["order"] = len(built)
            built.append(item)
    if not built:
        raise StepperError("capture needs at least one item")
    ids = [item["id"] for item in built]
    if len(ids) != len(set(ids)):
        raise StepperError("duplicate item id")
    built[0]["status"] = "active"
    created = now()
    ctx = {
        "version": VERSION,
        "id": context_id,
        "created_at": created,
        "updated_at": created,
        "closed": False,
        "paused": False,
        "lease": {"session_key": session_key, "acquired_at": created},
        "source_hash": source_hash,
        "next_seq": seq,
        "items": built,
    }
    save_context(root, ctx)
    if source_hash:
        suggestions = load_suggestions(root)
        suggestions["items"][source_hash]["status"] = "accepted"
        save_suggestions(root, suggestions)
    return result(ctx)


def cmd_add(root: Path, session_key: str, items: list[str], parent_id: str | None) -> dict:
    ctx = require_holder(root, session_key)
    if not items:
        raise StepperError("add needs at least one --item")
    parent = None
    if parent_id is not None:
        parent = _item(ctx, parent_id)
        if parent["status"] in ("verified", "cancelled"):
            raise StepperError(f"cannot add under {parent_id} because it is {parent['status']}")
    seq = ctx["next_seq"]
    for raw in items:
        item, seq = parse_item_arg(raw, seq)
        if any(existing["id"] == item["id"] for existing in ctx["items"]):
            raise StepperError(f"item {item['id']} already exists")
        item["parent_id"] = parent_id
        if parent is not None:
            depth = _depth(ctx, parent) + 1
            if depth > MAX_DEPTH:
                raise StepperError(
                    f"cannot add {item['id']} under {parent_id}: depth {depth} exceeds MAX_DEPTH {MAX_DEPTH}"
                )
        siblings = _children(ctx, parent_id)
        item["order"] = max((sibling["order"] for sibling in siblings), default=-1) + 1
        ctx["items"].append(item)
    ctx["next_seq"] = seq
    if not any(item["status"] == "active" for item in ctx["items"]):
        _activate_next(ctx)
    save_context(root, ctx)
    return result(ctx)


def cmd_focus(root: Path, session_key: str, item_id: str) -> dict:
    ctx = require_holder(root, session_key)
    item = _item(ctx, item_id)
    _guard_ancestors(ctx, item)
    blocking = _blocking_descendants(ctx, item, ("pending", "active", "blocked"))
    if blocking:
        raise StepperError(f"{item_id} has unresolved children; focus a leaf")
    if item["status"] != "active" and "active" not in LEGAL[item["status"]]:
        transition(ctx, item_id, "active")
    for ancestor in _ancestors(ctx, item):
        if ancestor["status"] == "deferred":
            ancestor["status"] = "pending"
    transition(ctx, item_id, "active")
    save_context(root, ctx)
    return result(ctx)


def cmd_verify(root: Path, session_key: str, item_id: str, evidence: str) -> dict:
    ctx = require_holder(root, session_key)
    transition(ctx, item_id, "verified", evidence=evidence)
    save_context(root, ctx)
    return result(ctx)


def cmd_block(root: Path, session_key: str, item_id: str, reason: str) -> dict:
    ctx = require_holder(root, session_key)
    transition(ctx, item_id, "blocked", reason=reason)
    save_context(root, ctx)
    return result(ctx)


def cmd_unblock(root: Path, session_key: str, item_id: str) -> dict:
    ctx = require_holder(root, session_key)
    item = _item(ctx, item_id)
    if item["status"] not in ("blocked", "pending"):
        raise StepperError(f"cannot unblock {item_id} from {item['status']}")
    transition(ctx, item_id, "pending")
    save_context(root, ctx)
    return result(ctx)


def cmd_defer(root: Path, session_key: str, item_id: str) -> dict:
    ctx = require_holder(root, session_key)
    transition(ctx, item_id, "deferred")
    save_context(root, ctx)
    return result(ctx)


def cmd_cancel(root: Path, session_key: str, item_id: str) -> dict:
    ctx = require_holder(root, session_key)
    transition(ctx, item_id, "cancelled")
    save_context(root, ctx)
    return result(ctx)


def cmd_pause(root: Path, session_key: str, paused: bool) -> dict:
    ctx = require_holder(root, session_key)
    ctx["paused"] = paused
    save_context(root, ctx)
    return result(ctx)


def cmd_close(root: Path, session_key: str) -> dict:
    ctx = require_holder(root, session_key)
    ctx["closed"] = True
    ctx["paused"] = False
    ctx["lease"] = None
    save_context(root, ctx)
    return result(ctx)


def cmd_detach(root: Path, session_key: str) -> dict:
    require_session(root, session_key)
    ctx = leased_by(root, session_key)
    if ctx is None:
        return {"ok": True, "context": None, "reminder": "Stepper: this session holds no context."}
    ctx["lease"] = None
    save_context(root, ctx)
    return result(ctx)


def cmd_attach(root: Path, session_key: str, context_id: str, take: bool) -> dict:
    require_session(root, session_key)
    current = leased_by(root, session_key)
    ctx = load_context(root, context_id)
    if ctx["closed"]:
        raise StepperError(f"context {context_id} is closed")
    if current and current["id"] != ctx["id"]:
        raise StepperError(
            f"session already holds {current['id']}; detach before attaching {context_id}"
        )
    lease = ctx["lease"]
    if lease and lease["session_key"] == session_key:
        return result(ctx)
    if lease and not take:
        raise StepperError(
            f"context {context_id} is held by {lease['session_key']}. "
            "Pass --take only after the user asks to continue that work in this session."
        )
    ctx["lease"] = {"session_key": session_key, "acquired_at": now()}
    save_context(root, ctx)
    return result(ctx)


def cmd_decline(root: Path, session_key: str, digest: str) -> dict:
    require_session(root, session_key)
    suggestions = load_suggestions(root)
    record = suggestions["items"].get(digest)
    if record and record["status"] == "accepted":
        raise StepperError(f"suggestion {digest} was already accepted")
    if record and record["status"] == "declined":
        return {"ok": True, "suggestion": digest, "status": "declined"}
    entries = (record or {}).get("entries") or []
    suggestions["items"][digest] = {
        "status": "declined",
        "count": (record or {}).get("count") or len(entries),
        "entries": entries,
        "session_key": session_key,
    }
    save_suggestions(root, suggestions)
    return {"ok": True, "suggestion": digest, "status": "declined"}


def cmd_status(root: Path, session_key: str | None, tree: bool = False) -> dict:
    ensure_store(root)
    contexts, corrupt = read_contexts(root)
    if session_key is None:
        return {
            "ok": True,
            "contexts": [
                {
                    "id": ctx["id"],
                    "closed": ctx["closed"],
                    "paused": ctx["paused"],
                    "lease": ctx["lease"],
                    "complete": is_complete(ctx),
                    "reminder": reminder(ctx),
                    "progress": {"top_level": _progress(ctx)["top_level"]},
                    **({"tree": [_tree_node(ctx, item) for item in _children(ctx, None)]} if tree else {}),
                }
                for ctx in contexts
            ],
            "corrupt_files": corrupt,
        }
    session = load_session(root, session_key)
    ctx = leased_by(root, session_key)
    return {
        "ok": True,
        "session": None
        if session is None
        else {"session_key": session_key, "prompt_class": session["prompt_class"]},
        "context": None if ctx is None else public_context(ctx),
        "reminder": None if ctx is None else reminder(ctx),
        "progress": None if ctx is None else _progress(ctx),
        **({"tree": [_tree_node(ctx, item) for item in _children(ctx, None)]} if tree and ctx is not None else {}),
        "corrupt_files": corrupt,
    }


def session_line(key: str) -> str:
    return f"Stepper session: {key}. Pass --session {key} on every stepper command."


def offer_line(candidate: dict) -> str:
    ids = [entry["id"] for entry in candidate["entries"] if entry["id"]]
    names = f" ({', '.join(ids)})" if ids else ""
    return (
        f"Stepper candidate {candidate['hash']}: {candidate['count']} items{names}. "
        "Ask the user once whether to track them. Do not capture until they accept."
    )


def mark_offered(root: Path, session_key: str, candidate: dict) -> None:
    status = suggestion_status(root, candidate["hash"])
    if status in ("offered", "accepted", "declined"):
        return
    suggestions = load_suggestions(root)
    suggestions["items"][candidate["hash"]] = {
        "status": "offered",
        "count": candidate["count"],
        "entries": candidate["entries"],
        "session_key": session_key,
    }
    save_suggestions(root, suggestions)


def release_lease(root: Path, session_key: str) -> None:
    ctx = leased_by(root, session_key)
    if ctx is None:
        return
    items = json.dumps(ctx["items"])
    ctx["lease"] = None
    save_context(root, ctx)
    saved = load_context(root, ctx["id"])
    if json.dumps(saved["items"]) != items:
        raise StepperError("lease release changed items")


def event_allowed(event: str, platform: str) -> bool:
    if platform == "cursor":
        return event in CURSOR_EVENTS
    if platform == "claude":
        return event in CLAUDE_EVENTS
    return False


def hook_root(payload: dict) -> Path:
    roots = payload.get("workspace_roots") or []
    if roots:
        return Path(str(roots[0])).expanduser().resolve()
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        return Path(cwd).expanduser().resolve()
    return Path.cwd()


def session_key_from(payload: dict, platform: str) -> str | None:
    if platform == "cursor":
        ident = payload.get("conversation_id") or payload.get("session_id")
        return f"cursor:{ident}" if ident else None
    ident = payload.get("session_id")
    return f"claude:{ident}" if ident else None


def generation_of(payload: dict) -> str | None:
    value = payload.get("generation_id") or payload.get("prompt_id")
    return str(value) if value else None


def consider_candidate(root: Path, sess: dict, candidate: dict | None, ctx: dict | None, generation: str | None) -> None:
    if not candidate:
        return
    status = suggestion_status(root, candidate["hash"])
    if status in ("offered", "accepted", "declined"):
        return
    if ctx is not None:
        sess["parked"] = candidate
        return
    sess["candidate"] = candidate
    sess["candidate_generation"] = generation


def handle_hook(root: Path, platform: str, payload: dict) -> dict | None:
    event = payload.get("hook_event_name") or ""
    if not event_allowed(event, platform):
        return None
    key = session_key_from(payload, platform)
    if not key:
        return None
    generation = generation_of(payload)
    if event in ("sessionEnd", "SessionEnd"):
        release_lease(root, key)
        return None
    if event in ("preCompact", "PreCompact"):
        sess = load_session(root, key)
        if sess is None:
            return None
        sess["compaction_pending"] = True
        save_session(root, sess)
        return None

    ctx = leased_by(root, key)
    holds = ctx is not None

    if event in ("beforeSubmitPrompt", "UserPromptSubmit"):
        prompt = payload.get("prompt") or ""
        if not holds and not is_stepper_prompt(prompt):
            return None
        sess = load_session(root, key) or fresh_session(key, platform)
        sess["prompt_class"] = classify(prompt, ctx)
        sess["generation_id"] = generation
        text = None
        if is_stepper_prompt(prompt):
            if platform == "cursor":
                sess["announce_key"] = True
            else:
                text = session_line(key)
        save_session(root, sess)
        return _hook_json(platform, event, text)

    if event == "afterAgentResponse":
        text = payload.get("text") or ""
        candidate = parse_candidates(text)
        sess = load_session(root, key)
        if sess is None and candidate is None:
            return None
        sess = sess or fresh_session(key, platform)
        sess["last_assistant_text"] = text
        sess["generation_id"] = generation
        consider_candidate(root, sess, candidate, ctx, generation)
        save_session(root, sess)
        return None

    if event in ("sessionStart", "SessionStart"):
        source = payload.get("source")
        if platform == "claude" and source not in (None, "startup", "resume", "compact"):
            return None
        if holds and ctx is not None and not ctx["paused"]:
            if has_outstanding(ctx) or any(item["status"] == "deferred" for item in ctx["items"]):
                text = reminder(ctx) + "\n" + session_line(key)
                return _hook_json(platform, event, text)
        # A restarted Claude session loses the earlier prompt injection. Repeat
        # the key when this session already registered, without tracking text.
        if (
            platform == "claude"
            and source in ("resume", "compact")
            and load_session(root, key) is not None
            and not (ctx and ctx["paused"])
        ):
            return _hook_json(platform, event, session_line(key))
        return None

    sess = load_session(root, key)

    if event in ("postToolUse", "PostToolUse"):
        if sess is None:
            return None
        parts = []
        if sess.get("announce_key"):
            parts.append(session_line(key))
            sess["announce_key"] = False
        if sess.get("compaction_pending") and holds and ctx is not None and not ctx["paused"]:
            parts.append(reminder(ctx))
            sess["compaction_pending"] = False
            sess["reminded_generation"] = generation
        candidate = sess.get("candidate")
        same_turn = (
            bool(candidate)
            and generation is not None
            and sess.get("candidate_generation") == generation
        )
        if same_turn and not holds and suggestion_status(root, candidate["hash"]) not in (
            "offered",
            "accepted",
            "declined",
        ):
            mark_offered(root, key, candidate)
            parts.append(offer_line(candidate))
            sess["candidate"] = None
        if parts:
            save_session(root, sess)
            return _hook_json(platform, event, "\n".join(parts))
        return None

    if event in ("stop", "Stop"):
        if payload.get("stop_hook_active") or int(payload.get("loop_count") or 0) > 0:
            return None
        assistant = payload.get("last_assistant_message") or ""
        if sess is None:
            # Claude has no afterAgentResponse. Detect here, and create a session
            # only when the final message contains a candidate that has not been
            # offered. An ordinary prompt writes nothing.
            found = parse_candidates(assistant) if assistant else None
            if found is None or suggestion_status(root, found["hash"]) in (
                "offered",
                "accepted",
                "declined",
            ):
                return None
            sess = fresh_session(key, platform)
        token = generation or "none"
        if sess.get("followup_generation") == token:
            return None
        if assistant:
            sess["last_assistant_text"] = assistant
            consider_candidate(root, sess, parse_candidates(assistant), ctx, generation)
        if holds and ctx["paused"]:
            save_session(root, sess)
            return None
        parts = []
        if (
            holds
            and not ctx["paused"]
            and sess.get("prompt_class") == "tracked"
            and has_outstanding(ctx)
            and sess.get("reminded_generation") != token
        ):
            parts.append(reminder(ctx))
            sess["reminded_generation"] = token
        if not holds:
            candidate = sess.get("candidate") or sess.get("parked")
            if candidate and suggestion_status(root, candidate["hash"]) not in (
                "offered",
                "accepted",
                "declined",
            ):
                mark_offered(root, key, candidate)
                parts.append(offer_line(candidate))
                sess["candidate"] = None
                sess["parked"] = None
        if not parts:
            save_session(root, sess)
            return None
        sess["followup_generation"] = token
        save_session(root, sess)
        return _hook_json(platform, event, "\n".join(parts))
    return None


def _hook_json(platform: str, event: str, text: str | None) -> dict | None:
    if not text:
        return None
    if platform == "cursor":
        if event == "stop":
            return {"followup_message": text}
        if event in ("sessionStart", "postToolUse"):
            return {"additional_context": text}
        return None
    if event in ("Stop", "SessionStart", "PostToolUse", "UserPromptSubmit"):
        return {
            "hookSpecificOutput": {
                "hookEventName": event,
                "additionalContext": text,
            }
        }
    return None


def hook_command(platform: str) -> str:
    script = Path(__file__).resolve()
    return (
        f"{shlex.quote(sys.executable)} {shlex.quote(str(script))} "
        f"hook --platform {platform} --tag stepper"
    )


def config_paths(platform: str) -> tuple[Path, Path]:
    base = home()
    if platform == "cursor":
        return base / ".cursor" / "hooks.json", base / ".stepper" / "hook-install.json"
    return base / ".claude" / "settings.json", base / ".stepper" / "hook-install.json"


def load_receipt() -> dict:
    path = home() / ".stepper" / "hook-install.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_receipt(data: dict) -> None:
    path = home() / ".stepper" / "hook-install.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(data, indent=2) + "\n")


def ours(command: str | None, platform: str) -> bool:
    return bool(command and "--tag stepper" in command and f"--platform {platform}" in command)


def read_settings(path: Path) -> tuple[dict, bool]:
    if not path.exists():
        return {}, False
    raw = path.read_bytes()
    try:
        data = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StepperError(f"refusing to edit {path}: not valid JSON") from exc
    if not isinstance(data, dict):
        raise StepperError(f"refusing to edit {path}: expected a JSON object")
    return data, True


def backup(path: Path, platform: str) -> None:
    if not path.exists():
        return
    dest = home() / ".stepper" / "backups" / f"{platform}-{stamp()}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(path.read_bytes())


def write_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, json.dumps(data, indent=2) + "\n")


def install_hooks(platform: str) -> dict:
    path, _receipt_path = config_paths(platform)
    data, existed = read_settings(path)
    added_hooks_key = existed and "hooks" not in data
    command = hook_command(platform)
    hooks = data.setdefault("hooks", {})
    if platform == "cursor":
        if "version" not in data and not existed:
            data["version"] = 1
        specs = {
            "sessionStart": {},
            "sessionEnd": {},
            "beforeSubmitPrompt": {},
            "afterAgentResponse": {},
            "postToolUse": {},
            "stop": {"loop_limit": 1},
            "preCompact": {},
        }
        for event, extra in specs.items():
            entries = hooks.setdefault(event, [])
            if any(entry.get("command") == command for entry in entries):
                continue
            entry = {"command": command}
            entry.update(extra)
            entries.append(entry)
    else:
        groups = {
            "SessionStart": "startup|resume|compact",
            "SessionEnd": None,
            "UserPromptSubmit": None,
            "PostToolUse": None,
            "Stop": None,
            "PreCompact": None,
        }
        for event, matcher in groups.items():
            found = None
            for group in hooks.setdefault(event, []):
                if group.get("matcher") == matcher or (matcher is None and "matcher" not in group):
                    found = group
                    break
            if found is None:
                found = {"hooks": []}
                if matcher:
                    found["matcher"] = matcher
                hooks[event].append(found)
            if any(item.get("command") == command for item in found["hooks"]):
                continue
            found["hooks"].append({"type": "command", "command": command})
    backup(path, platform)
    write_settings(path, data)
    receipt = load_receipt()
    receipt[platform] = {
        "path": str(path),
        "created_file": not existed,
        "added_hooks_key": added_hooks_key,
    }
    save_receipt(receipt)
    return {"ok": True, "platform": platform, "path": str(path), "installed": True}


def _strip_cursor(hooks: dict, platform: str) -> None:
    for event in list(hooks):
        kept = [entry for entry in hooks[event] if not ours(entry.get("command"), platform)]
        if kept:
            hooks[event] = kept
        else:
            del hooks[event]


def _strip_claude(hooks: dict, platform: str) -> None:
    for event in list(hooks):
        kept_groups = []
        for group in hooks[event]:
            if "hooks" not in group:
                kept_groups.append(group)
                continue
            group["hooks"] = [
                item for item in group["hooks"] if not ours(item.get("command"), platform)
            ]
            if group["hooks"]:
                kept_groups.append(group)
        if kept_groups:
            hooks[event] = kept_groups
        else:
            del hooks[event]


def uninstall_hooks(platform: str) -> dict:
    path, _receipt_path = config_paths(platform)
    if not path.exists():
        return {"ok": True, "platform": platform, "path": str(path), "installed": False}
    data, _existed = read_settings(path)
    receipt = load_receipt().get(platform) or {}
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        if platform == "cursor":
            _strip_cursor(hooks, platform)
        else:
            _strip_claude(hooks, platform)
        if not hooks and receipt.get("added_hooks_key"):
            data.pop("hooks", None)
    backup(path, platform)
    if isinstance(data.get("hooks"), dict) and not data["hooks"]:
        data.pop("hooks", None)
    leftover = {
        key: value
        for key, value in data.items()
        if not (key == "version" and receipt.get("created_file"))
    }
    if receipt.get("created_file") and not leftover:
        path.unlink()
    else:
        write_settings(path, data)
    return {"ok": True, "platform": platform, "path": str(path), "installed": False}


def hooks_status() -> dict:
    report = {"ok": True}
    for platform in ("cursor", "claude"):
        path, _receipt = config_paths(platform)
        installed = []
        if path.exists():
            try:
                data, _existed = read_settings(path)
            except StepperError as exc:
                report[platform] = {"path": str(path), "error": str(exc)}
                continue
            hooks = data.get("hooks") or {}
            if platform == "cursor":
                for event, entries in hooks.items():
                    if any(ours(entry.get("command"), platform) for entry in entries):
                        installed.append(event)
            else:
                for event, groups in hooks.items():
                    for group in groups:
                        if any(ours(item.get("command"), platform) for item in group.get("hooks") or []):
                            installed.append(event)
        report[platform] = {"path": str(path), "installed": bool(installed), "events": installed}
    return report


def emit(data: dict, code: int = 0) -> int:
    sys.stdout.write(json.dumps(data, indent=2) + "\n")
    return code


def run_command(args: argparse.Namespace) -> dict:
    root = resolve_root(args.root)
    with locked(root, block=True):
        if args.cmd == "capture":
            return cmd_capture(root, args.session, args.context, args.item or [], args.suggestion)
        if args.cmd == "add":
            return cmd_add(root, args.session, args.item or [], args.parent)
        if args.cmd == "status":
            return cmd_status(root, args.session, args.tree)
        if args.cmd == "focus":
            return cmd_focus(root, args.session, args.item_id)
        if args.cmd == "verify":
            return cmd_verify(root, args.session, args.item_id, args.evidence)
        if args.cmd == "block":
            return cmd_block(root, args.session, args.item_id, args.reason)
        if args.cmd == "unblock":
            return cmd_unblock(root, args.session, args.item_id)
        if args.cmd == "defer":
            return cmd_defer(root, args.session, args.item_id)
        if args.cmd == "cancel":
            return cmd_cancel(root, args.session, args.item_id)
        if args.cmd == "pause":
            return cmd_pause(root, args.session, True)
        if args.cmd == "resume":
            return cmd_pause(root, args.session, False)
        if args.cmd == "close":
            return cmd_close(root, args.session)
        if args.cmd == "attach":
            return cmd_attach(root, args.session, args.context_id, args.take)
        if args.cmd == "detach":
            return cmd_detach(root, args.session)
        if args.cmd == "decline":
            return cmd_decline(root, args.session, args.hash)
        raise StepperError(f"unknown command {args.cmd}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stepper")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def root(command: argparse.ArgumentParser) -> None:
        command.add_argument("--root")

    def session(command: argparse.ArgumentParser, required: bool = True) -> None:
        command.add_argument("--session", required=required)

    capture = sub.add_parser("capture")
    root(capture)
    session(capture)
    capture.add_argument("--context", default="default")
    capture.add_argument("--item", action="append")
    capture.add_argument("--suggestion")

    add = sub.add_parser("add")
    root(add)
    session(add)
    add.add_argument("--item", action="append")
    add.add_argument("--parent")

    status = sub.add_parser("status")
    root(status)
    session(status, required=False)
    status.add_argument("--tree", action="store_true")

    for name in ("focus", "unblock", "defer", "cancel"):
        command = sub.add_parser(name)
        root(command)
        session(command)
        command.add_argument("item_id")

    verify = sub.add_parser("verify")
    root(verify)
    session(verify)
    verify.add_argument("item_id")
    verify.add_argument("--evidence", required=True)

    block = sub.add_parser("block")
    root(block)
    session(block)
    block.add_argument("item_id")
    block.add_argument("--reason", required=True)

    for name in ("pause", "resume", "close", "detach"):
        command = sub.add_parser(name)
        root(command)
        session(command)

    attach = sub.add_parser("attach")
    root(attach)
    session(attach)
    attach.add_argument("context_id")
    attach.add_argument("--take", action="store_true")

    decline = sub.add_parser("decline")
    root(decline)
    session(decline)
    decline.add_argument("hash")

    hook = sub.add_parser("hook")
    hook.add_argument("--platform", required=True, choices=("cursor", "claude"))
    hook.add_argument("--tag")

    hooks = sub.add_parser("hooks")
    hook_sub = hooks.add_subparsers(dest="hooks_cmd", required=True)
    for name in ("install", "uninstall"):
        command = hook_sub.add_parser(name)
        command.add_argument("platform", choices=("cursor", "claude"))
    hook_sub.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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
            try:
                with locked(root, block=False):
                    output = handle_hook(root, args.platform, payload)
            except StepperError:
                return 0
            if output:
                sys.stdout.write(json.dumps(output) + "\n")
            return 0
        if args.cmd == "hooks":
            if args.hooks_cmd == "install":
                return emit(install_hooks(args.platform))
            if args.hooks_cmd == "uninstall":
                return emit(uninstall_hooks(args.platform))
            return emit(hooks_status())
        return emit(run_command(args))
    except StepperError as exc:
        return emit({"ok": False, "error": str(exc)}, 1)


if __name__ == "__main__":
    sys.exit(main())
