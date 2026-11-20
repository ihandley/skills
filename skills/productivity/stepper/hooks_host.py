"""Install, uninstall and check agent hooks in a host's settings file.

One module, two adapters (Claude, Cursor). A caller passes the tag that marks
its commands, a state directory for the receipt and backups, and the events to
register. The settings-file shape, the receipt, the backup and the atomic write
stay in here.

This file is copied into each skill that installs hooks, so every skill installs
on its own. The copies must stay identical.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

PLATFORMS = ("cursor", "claude")


class HostError(Exception):
    pass


@dataclass(frozen=True)
class Event:
    """One hook event. ``matcher`` is Claude only. ``extra`` is Cursor only."""

    name: str
    matcher: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Spec:
    """What one caller installs.

    tag        marks this caller's commands (``--tag <tag>``)
    state_dir  holds ``hook-install.json`` and ``backups/``
    script     the file the hook command runs
    events     {platform: [Event, ...]}
    """

    tag: str
    state_dir: Path
    script: Path
    events: dict


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def settings_path(home: Path, platform: str) -> Path:
    if platform == "cursor":
        return home / ".cursor" / "hooks.json"
    return home / ".claude" / "settings.json"


def hook_command(spec: Spec, platform: str) -> str:
    return (
        f"{shlex.quote(sys.executable)} {shlex.quote(str(spec.script))} "
        f"hook --platform {platform} --tag {spec.tag}"
    )


def ours(spec: Spec, command: str | None, platform: str) -> bool:
    return bool(command and f"--tag {spec.tag}" in command and f"--platform {platform}" in command)


def _receipt_path(spec: Spec) -> Path:
    return spec.state_dir / "hook-install.json"


def load_receipt(spec: Spec) -> dict:
    path = _receipt_path(spec)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _save_receipt(spec: Spec, data: dict) -> None:
    atomic_write(_receipt_path(spec), json.dumps(data, indent=2) + "\n")


def read_settings(path: Path) -> tuple[dict, bool]:
    if not path.exists():
        return {}, False
    try:
        data = json.loads(path.read_bytes().decode())
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HostError(f"refusing to edit {path}: not valid JSON") from exc
    if not isinstance(data, dict):
        raise HostError(f"refusing to edit {path}: expected a JSON object")
    return data, True


def _backup(spec: Spec, path: Path, platform: str) -> None:
    if not path.exists():
        return
    dest = spec.state_dir / "backups" / f"{platform}-{_stamp()}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(path.read_bytes())


def _write_settings(path: Path, data: dict) -> None:
    atomic_write(path, json.dumps(data, indent=2) + "\n")


def _drop(spec: Spec, command: str | None, platform: str, keep: str | None) -> bool:
    return ours(spec, command, platform) and command != keep


# ---------------------------------------------------------------- adapters

class CursorAdapter:
    platform = "cursor"

    def add(self, spec: Spec, data: dict, existed: bool, command: str) -> None:
        if "version" not in data and not existed:
            data["version"] = 1
        hooks = data.setdefault("hooks", {})
        for event in spec.events.get("cursor", []):
            entries = hooks.setdefault(event.name, [])
            if any(entry.get("command") == command for entry in entries):
                continue
            entries.append({"command": command, **event.extra})

    def strip(self, spec: Spec, hooks: dict, keep: str | None = None) -> None:
        for name in list(hooks):
            kept = [e for e in hooks[name] if not _drop(spec, e.get("command"), self.platform, keep)]
            if kept:
                hooks[name] = kept
            else:
                del hooks[name]

    def installed_events(self, spec: Spec, hooks: dict) -> list[str]:
        return [name for name, entries in hooks.items()
                if any(ours(spec, e.get("command"), self.platform) for e in entries)]


class ClaudeAdapter:
    platform = "claude"

    def add(self, spec: Spec, data: dict, existed: bool, command: str) -> None:
        hooks = data.setdefault("hooks", {})
        for event in spec.events.get("claude", []):
            found = None
            for group in hooks.setdefault(event.name, []):
                if group.get("matcher") == event.matcher or (event.matcher is None and "matcher" not in group):
                    found = group
                    break
            if found is None:
                found = {"hooks": []}
                if event.matcher:
                    found["matcher"] = event.matcher
                hooks[event.name].append(found)
            if any(item.get("command") == command for item in found["hooks"]):
                continue
            found["hooks"].append({"type": "command", "command": command})

    def strip(self, spec: Spec, hooks: dict, keep: str | None = None) -> None:
        for name in list(hooks):
            kept_groups = []
            for group in hooks[name]:
                if "hooks" not in group:
                    kept_groups.append(group)
                    continue
                group["hooks"] = [i for i in group["hooks"]
                                  if not _drop(spec, i.get("command"), self.platform, keep)]
                if group["hooks"]:
                    kept_groups.append(group)
            if kept_groups:
                hooks[name] = kept_groups
            else:
                del hooks[name]

    def installed_events(self, spec: Spec, hooks: dict) -> list[str]:
        found = []
        for name, groups in hooks.items():
            for group in groups:
                if any(ours(spec, i.get("command"), self.platform) for i in group.get("hooks") or []):
                    found.append(name)
        return found


ADAPTERS = {"cursor": CursorAdapter(), "claude": ClaudeAdapter()}


# ---------------------------------------------------------------- operations

def install_settings(spec: Spec, home: Path, platform: str) -> dict:
    """Write this caller's command into the platform settings file.

    Cursor still uses this. Claude does not: the plugin's ``hooks/hooks.json``
    is the only Claude owner, and ``install`` for Claude only removes leftovers.
    """
    path = settings_path(home, platform)
    data, existed = read_settings(path)
    added_hooks_key = existed and "hooks" not in data
    command = hook_command(spec, platform)
    if isinstance(data.get("hooks"), dict):
        # A reinstall replaces a stale command (another interpreter or path) instead of stacking.
        ADAPTERS[platform].strip(spec, data["hooks"], keep=command)
    ADAPTERS[platform].add(spec, data, existed, command)
    _backup(spec, path, platform)
    _write_settings(path, data)
    receipt = load_receipt(spec)
    receipt[platform] = {"path": str(path), "created_file": not existed, "added_hooks_key": added_hooks_key}
    _save_receipt(spec, receipt)
    return {"ok": True, "platform": platform, "path": str(path), "installed": True}


def _hook_commands(hooks: dict) -> list[tuple[str, str]]:
    found = []
    if not isinstance(hooks, dict):
        return found
    for name, groups in hooks.items():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for item in group.get("hooks") or []:
                command = item.get("command") if isinstance(item, dict) else None
                if isinstance(command, str):
                    found.append((name, command))
    return found


def plugin_claim(spec: Spec) -> dict | None:
    """The plugin hooks file that runs this caller, when this script lives inside one."""
    script = spec.script.resolve()
    for parent in script.parents:
        if not (parent / ".claude-plugin" / "plugin.json").is_file():
            continue
        hooks_file = parent / "hooks" / "hooks.json"
        if not hooks_file.is_file():
            return None
        try:
            rel = script.relative_to(parent).as_posix()
        except ValueError:
            return None
        try:
            data = json.loads(hooks_file.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        hooks = data.get("hooks") if isinstance(data, dict) else None
        tag = f"--tag {spec.tag}"
        events = []
        for name, command in _hook_commands(hooks or {}):
            if rel in command and tag in command and "--platform claude" in command:
                if name not in events:
                    events.append(name)
        if not events:
            return None
        return {"path": str(hooks_file), "events": events}
    return None


def install_claude(spec: Spec, home: Path) -> dict:
    """Drop leftover Claude settings entries. The plugin file is the install."""
    path = settings_path(home, "claude")
    if path.exists():
        read_settings(path)
        uninstall(spec, home, "claude")
    claim = plugin_claim(spec)
    return {
        "ok": True,
        "platform": "claude",
        "path": claim["path"] if claim else str(path),
        "installed": claim is not None,
        "source": "plugin" if claim else "absent",
    }


def install(spec: Spec, home: Path, platform: str) -> dict:
    if platform == "claude":
        return install_claude(spec, home)
    return install_settings(spec, home, platform)


def uninstall(spec: Spec, home: Path, platform: str) -> dict:
    path = settings_path(home, platform)
    if not path.exists():
        return {"ok": True, "platform": platform, "path": str(path), "installed": False}
    data, _existed = read_settings(path)
    receipt = load_receipt(spec).get(platform) or {}
    hooks = data.get("hooks")
    if isinstance(hooks, dict):
        ADAPTERS[platform].strip(spec, hooks)
        if not hooks and receipt.get("added_hooks_key"):
            data.pop("hooks", None)
    _backup(spec, path, platform)
    if isinstance(data.get("hooks"), dict) and not data["hooks"]:
        data.pop("hooks", None)
    leftover = {k: v for k, v in data.items() if not (k == "version" and receipt.get("created_file"))}
    if receipt.get("created_file") and not leftover:
        path.unlink()
    else:
        _write_settings(path, data)
    return {"ok": True, "platform": platform, "path": str(path), "installed": False}


def _settings_report(spec: Spec, home: Path, platform: str) -> dict:
    path = settings_path(home, platform)
    events: list[str] = []
    if path.exists():
        try:
            data, _existed = read_settings(path)
        except HostError as exc:
            return {"path": str(path), "error": str(exc)}
        events = ADAPTERS[platform].installed_events(spec, data.get("hooks") or {})
    return {"path": str(path), "installed": bool(events), "events": events}


def status(spec: Spec, home: Path) -> dict:
    report = {"ok": True}
    claim = plugin_claim(spec)
    for platform in PLATFORMS:
        if platform == "claude" and claim:
            legacy = _settings_report(spec, home, "claude")
            entry = {
                "path": claim["path"],
                "installed": True,
                "source": "plugin",
                "events": claim["events"],
            }
            if "error" in legacy:
                entry["error"] = legacy["error"]
                entry["legacy_settings"] = True
            else:
                entry["legacy_settings"] = bool(legacy["events"])
            report["claude"] = entry
            continue
        report[platform] = _settings_report(spec, home, platform)
    return report
