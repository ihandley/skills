"""The lifecycle of a Stepper context id.

One place decides what an id means and what may happen to it. States:

    FREE           no live file, nothing archived under the id
    ARCHIVED       no live file, an earlier context with the id was archived
    HELD_BY_ME     open, leased to this session
    HELD_BY_OTHER  open, leased to another session
    OPEN_UNHELD    open, leased to nobody
    CLOSED         a live file marked closed
    CORRUPT        a live file that cannot be read as a context

The module reads and moves files under the store. It never decides what is in a
context; ``load`` does that and raises the caller's corrupt-file error.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable


class State(str, Enum):
    FREE = "free"
    ARCHIVED = "archived"
    HELD_BY_ME = "held_by_me"
    HELD_BY_OTHER = "held_by_other"
    OPEN_UNHELD = "open_unheld"
    CLOSED = "closed"
    CORRUPT = "corrupt"


@dataclass(frozen=True)
class Inspection:
    state: State
    ctx: dict | None = None
    error: Exception | None = None


def held_by(contexts: list[dict], session_key: str) -> list[dict]:
    return [
        ctx for ctx in contexts
        if ctx["lease"] and ctx["lease"]["session_key"] == session_key and not ctx["closed"]
    ]


def release(ctx: dict) -> dict:
    ctx["lease"] = None
    return ctx


def take(ctx: dict, session_key: str, acquired_at: str) -> dict:
    ctx["lease"] = {"session_key": session_key, "acquired_at": acquired_at}
    return ctx


class ContextIds:
    def __init__(self, live: Path, archive: Path, load: Callable[[str], dict], stamp: Callable[[], str],
                 refuse: Callable[[str, dict], Exception], corrupt_types: tuple[type, ...]):
        self.live, self.archive_dir, self._load, self._stamp = live, archive, load, stamp
        self._refuse, self._corrupt = refuse, corrupt_types

    def live_path(self, context_id: str) -> Path:
        return self.live / f"{context_id}.json"

    def archived(self, context_id: str) -> list[dict]:
        """The archived contexts for an id, oldest first. Callers do not depend on where they are kept."""
        if not self.archive_dir.is_dir():
            return []
        import json
        found = sorted(self.archive_dir.glob(f"{context_id}-*.json"))
        return [json.loads(path.read_text()) for path in found]

    def inspect(self, context_id: str, session_key: str) -> Inspection:
        if not self.live_path(context_id).exists():
            return Inspection(State.ARCHIVED if self.archived(context_id) else State.FREE)
        try:
            ctx = self._load(context_id)
        except self._corrupt as exc:
            return Inspection(State.CORRUPT, None, exc)
        if ctx["closed"]:
            return Inspection(State.CLOSED, ctx)
        lease = ctx["lease"]
        if not lease:
            return Inspection(State.OPEN_UNHELD, ctx)
        mine = lease["session_key"] == session_key
        return Inspection(State.HELD_BY_ME if mine else State.HELD_BY_OTHER, ctx)

    def check_claim(self, context_id: str, session_key: str) -> Inspection:
        """Raise unless the id can be claimed. A closed id can: claiming archives it."""
        seen = self.inspect(context_id, session_key)
        if seen.state is State.CORRUPT:
            raise seen.error
        if seen.state in (State.HELD_BY_ME, State.HELD_BY_OTHER, State.OPEN_UNHELD):
            raise self._refuse(context_id, seen.ctx)
        return seen

    def archive_live(self, context_id: str) -> None:
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        os.replace(self.live_path(context_id), self.archive_dir / f"{context_id}-{self._stamp()}.json")

    def check_attach(self, context_id: str, session_key: str, take_it: bool, missing: Exception,
                     closed: Exception, held: Callable[[dict], Exception]) -> Inspection:
        """Raise unless this session may hold the id. HELD_BY_ME passes through untouched."""
        seen = self.inspect(context_id, session_key)
        if seen.state is State.CORRUPT:
            raise seen.error
        if seen.state in (State.FREE, State.ARCHIVED):
            raise missing
        if seen.state is State.CLOSED:
            raise closed
        if seen.state is State.HELD_BY_OTHER and not take_it:
            raise held(seen.ctx)
        return seen
