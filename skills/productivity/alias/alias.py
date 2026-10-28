#!/usr/bin/env python3
"""Name-to-id cache. Tool bindings live in config. The script has no service names.

Cache YAML is a subset: comments, scalars, inline lists, and one nested map
(`ids`). Parsed here so a hook does not need PyYAML.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import hooks_host  # noqa: E402

TAG = "alias"
CLAUDE_SESSION_MATCHER = "startup|resume|compact|clear|fork"


class AliasError(Exception):
    pass


def home() -> Path:
    override = os.environ.get("ALIAS_HOME")
    return Path(override) if override else Path.home()


def config_path() -> Path:
    override = os.environ.get("ALIAS_CONFIG")
    if override:
        return Path(override)
    return home() / ".config" / "alias" / "config.yaml"


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path))


def needs_quote(text: str) -> bool:
    if text == "" or text.strip() != text:
        return True
    if text in ("true", "false", "null", "~"):
        return True
    return bool(re.search(r"[:#\[\]\{\}&*!|>%@`'\",]|^\s|\s$", text)) or "\n" in text


def dump_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    text = str(value)
    if needs_quote(text):
        return "'" + text.replace("'", "''") + "'"
    return text


def parse_scalar(raw: str):
    value = raw.strip()
    if value in ("true", "false"):
        return value == "true"
    if len(value) >= 2 and value[0] == value[-1] == "'":
        inner = value[1:-1]
        return inner.replace("''", "'").replace("\\'", "'")
    if len(value) >= 2 and value[0] == value[-1] == '"':
        inner = value[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    return value


def parse_flow(raw: str) -> list:
    inner = raw.strip()[1:-1]
    if not inner.strip():
        return []
    items = []
    buf: list[str] = []
    quote = None
    for ch in inner:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch == ",":
            items.append(parse_scalar("".join(buf).strip()))
            buf = []
            continue
        buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        items.append(parse_scalar(tail))
    return items


def dump_flow(items: list) -> str:
    return "[" + ", ".join(dump_scalar(item) for item in items) + "]"


def load_cache(path: Path) -> dict:
    entries: dict = {}
    if not path.exists():
        return entries
    current_key = None
    current = None
    nested = None
    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and raw_line.rstrip().endswith(":"):
            if current_key is not None:
                entries[current_key] = current
            current_key = raw_line[:-1].strip()
            current = {"aliases": []}
            nested = None
            continue
        if current is None or ":" not in raw_line:
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        field, _, value = raw_line.strip().partition(":")
        field = field.strip()
        value = value.strip()
        if indent >= 4 and nested:
            current[nested][field] = parse_scalar(value)
            continue
        nested = None
        if value == "":
            nested = field
            current[field] = {}
            continue
        if value.startswith("["):
            current[field] = parse_flow(value)
            continue
        current[field] = parse_scalar(value)
    if current_key is not None:
        entries[current_key] = current
    return entries


def dump_cache(path: Path, entries: dict) -> None:
    lines = [
        "# Alias cache. ids.<name> is the value a configured tool reads and writes.",
        "# pronouns is a person field. Other fields are notes. Unreviewed rows are marked.",
        "",
    ]
    for key, data in entries.items():
        lines.append(f"{key}:")
        aliases = data.get("aliases") or []
        lines.append(f"  aliases: {dump_flow(aliases)}")
        if "type" in data:
            lines.append(f"  type: {dump_scalar(data['type'])}")
        if data.get("pronouns"):
            lines.append(f"  pronouns: {dump_scalar(data['pronouns'])}")
        for field in sorted(data):
            if field in ("aliases", "type", "pronouns", "ids", "_stub", "_raw"):
                continue
            value = data[field]
            if isinstance(value, list):
                lines.append(f"  {field}: {dump_flow(value)}")
            elif isinstance(value, dict):
                lines.append(f"  {field}:")
                for child, child_value in value.items():
                    lines.append(f"    {child}: {dump_scalar(child_value)}")
            else:
                lines.append(f"  {field}: {dump_scalar(value)}")
        ids = data.get("ids") or {}
        if ids:
            lines.append("  ids:")
            for name in sorted(ids):
                lines.append(f"    {name}: {dump_scalar(ids[name])}")
        if data.get("_stub"):
            lines.append("  _stub: true")
        if "_raw" in data:
            lines.append(f"  _raw: {dump_scalar(data['_raw'])}")
        lines.append("")
    text = "\n".join(lines).rstrip() + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".alias-")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def _contains_as_phrase(haystack: str, needle: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(needle) + r"(?!\w)"
    return re.search(pattern, haystack) is not None


def find_match(entries: dict, query: str, type_filter: str | None = None):
    q = query.strip().lower()
    if not q:
        return None, None
    best = None
    for key, data in entries.items():
        if type_filter is not None and data.get("type") != type_filter:
            continue
        candidates = [key.replace("_", " ")] + list(data.get("aliases") or [])
        for candidate in candidates:
            cl = str(candidate).strip().lower()
            if not cl:
                continue
            if q == cl:
                score = (2, len(cl))
            elif _contains_as_phrase(cl, q):
                score = (1, len(cl))
            elif _contains_as_phrase(q, cl):
                score = (0, len(cl))
            else:
                continue
            if best is None or score > best[0]:
                best = (score, key, data)
    if best is None:
        return None, None
    return best[1], best[2]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return slug or "unknown"


def unique_slug(entries: dict, name: str) -> str:
    slug = base = slugify(name)
    n = 2
    while slug in entries:
        slug = f"{base}_{n}"
        n += 1
    return slug


def is_stub(data: dict) -> bool:
    return data.get("_stub") in (True, "true")


def load_config(path: Path | None = None) -> dict:
    path = path or config_path()
    if not path.exists():
        raise AliasError(f"config not found: {path}")
    data: dict = {"tools": []}
    current = None
    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - "):
            current = {}
            data["tools"].append(current)
            rest = raw_line.strip()[2:]
            if ":" in rest:
                key, _, value = rest.partition(":")
                current[key.strip()] = parse_scalar(value.strip())
            continue
        if raw_line.startswith("    ") and current is not None and ":" in raw_line:
            key, _, value = raw_line.strip().partition(":")
            current[key.strip()] = parse_scalar(value.strip())
            continue
        if not raw_line.startswith(" ") and raw_line.rstrip().endswith(":"):
            key = raw_line[:-1].strip()
            if key != "tools":
                raise AliasError(f"unknown config key: {key}")
            current = None
            continue
        if not raw_line.startswith(" ") and ":" in raw_line:
            key, _, value = raw_line.partition(":")
            data[key.strip()] = parse_scalar(value.strip())
            current = None
    if "cache" not in data:
        raise AliasError("config missing cache")
    for tool in data["tools"]:
        for field in ("tool", "query", "type", "id", "extract"):
            if not tool.get(field):
                raise AliasError(f"tool binding missing {field}")
        try:
            pattern = re.compile(tool["extract"])
        except re.error as exc:
            raise AliasError(f"bad extract for {tool.get('tool')}: {exc}") from exc
        if pattern.groups != 1:
            raise AliasError(f"extract for {tool.get('tool')} needs one capture group")
    return data


def cache_path(config: dict) -> Path:
    return expand(str(config["cache"]))


def binding_for(config: dict, tool_name: str) -> dict | None:
    for tool in config["tools"]:
        if tool["tool"] == tool_name:
            return tool
    return None


def public_entry(key: str, data: dict) -> dict:
    out = {"match": key}
    for field, value in data.items():
        if field.startswith("_"):
            continue
        out[field] = value
    return out


def projection(entries: dict) -> str:
    lines = [
        "Alias cache. Refer to a listed person with their pronouns. "
        "If pronouns is absent, use their name and ask once this session what to record. "
        "Do not use singular they for a person listed here. "
        "Do not call a lookup tool when the id it would fetch is already shown."
    ]
    any_row = False
    for key, data in entries.items():
        if is_stub(data):
            continue
        any_row = True
        parts = [key, f"type={data.get('type', '')}"]
        aliases = data.get("aliases") or []
        if aliases:
            parts.append("aliases=[" + ", ".join(str(a) for a in aliases) + "]")
        if data.get("pronouns"):
            parts.append(f"pronouns={data['pronouns']}")
        for name, value in sorted((data.get("ids") or {}).items()):
            parts.append(f"ids.{name}={value}")
        lines.append("- " + " ".join(parts))
    if not any_row:
        return ""
    return "\n".join(lines)


def assign_field(fields: dict, key: str, value: str) -> None:
    if key.startswith("_"):
        raise AliasError(f"refusing private field {key}")
    if key.startswith("ids."):
        name = key.split(".", 1)[1]
        if not name:
            raise AliasError("ids field needs a name")
        fields.setdefault("ids", {})[name] = value
        return
    fields[key] = value


def cmd_get(query: str) -> dict:
    config = load_config()
    key, data = find_match(load_cache(cache_path(config)), query)
    if not key:
        return {"match": None}
    return public_entry(key, data)


def cmd_add(entry_type: str, name: str, pairs: list[str]) -> dict:
    config = load_config()
    path = cache_path(config)
    entries = load_cache(path)
    existing, _ = find_match(entries, name, type_filter=entry_type)
    if existing:
        raise AliasError(f"already cached as '{existing}'. Edit the cache file to change it.")
    fields: dict = {"aliases": [name], "type": entry_type}
    for pair in pairs:
        if "=" not in pair:
            raise AliasError(f"expected field=value: {pair}")
        key, _, value = pair.partition("=")
        assign_field(fields, key.strip(), value.strip())
    slug = unique_slug(entries, name)
    entries[slug] = fields
    dump_cache(path, entries)
    return {"added": slug}


def payload_tool(payload: dict) -> str:
    return str(payload.get("tool_name") or payload.get("toolName") or "")


def payload_input(payload: dict) -> dict:
    for key in ("tool_input", "toolInput", "arguments", "args"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def payload_text(payload: dict) -> str:
    for key in ("tool_response", "toolResponse", "result", "output"):
        if key in payload and payload[key] not in (None, ""):
            value = payload[key]
            if isinstance(value, str):
                return value
            return json.dumps(value, ensure_ascii=False)
    return ""


def event_name(payload: dict) -> str:
    raw = payload.get("hook_event_name") or payload.get("hookEventName") or ""
    return str(raw).lower()


def hook_session(entries: dict, platform: str) -> dict | None:
    text = projection(entries)
    if not text:
        return None
    if platform == "cursor":
        return {"additional_context": text}
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": text,
        }
    }


def hook_pre(entry_key: str, data: dict, binding: dict, platform: str) -> dict | None:
    ids = data.get("ids") or {}
    id_name = binding["id"]
    if not ids.get(id_name):
        return None
    shown = public_entry(entry_key, data)
    reason = f"Cached alias '{entry_key}': " + ", ".join(
        f"{k}={v}" for k, v in shown.items() if k != "match"
    )
    if platform == "cursor":
        return {"permission": "deny", "agent_message": reason, "user_message": reason}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def apply_post(entries: dict, binding: dict, query: str, response: str) -> str | None:
    matches = re.findall(binding["extract"], response)
    key, data = find_match(entries, query, type_filter=binding["type"])
    id_name = binding["id"]
    if len(matches) != 1:
        if key and not is_stub(data):
            return None
        raw = response.replace("\n", " ")[:2000]
        if key and is_stub(data):
            data["_raw"] = raw
            return f"Alias stub '{key}' still unresolved ({len(matches)} matches)."
        slug = unique_slug(entries, query)
        entries[slug] = {
            "aliases": [query],
            "type": binding["type"],
            "_stub": True,
            "_raw": raw,
        }
        return f"Alias stub '{slug}' saved ({len(matches)} matches). Edit the cache to record the id."
    value = matches[0]
    if not key:
        slug = unique_slug(entries, query)
        entries[slug] = {
            "aliases": [query],
            "type": binding["type"],
            "ids": {id_name: value},
        }
        return f"Alias cached {slug} ids.{id_name}={value}"
    ids = data.setdefault("ids", {})
    if ids.get(id_name):
        return None
    ids[id_name] = value
    if is_stub(data):
        data.pop("_stub", None)
        data.pop("_raw", None)
    return f"Alias updated {key} ids.{id_name}={value}"


def hook_post_message(message: str | None, platform: str) -> dict | None:
    if not message:
        return None
    if platform == "cursor":
        return {"additional_context": message}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    }


def cmd_hook(platform: str) -> dict | None:
    payload = json.load(sys.stdin)
    try:
        config = load_config()
    except AliasError as exc:
        print(str(exc), file=sys.stderr)
        return None
    event = event_name(payload)
    entries = load_cache(cache_path(config))
    if event in ("sessionstart",):
        return hook_session(entries, platform)
    binding = binding_for(config, payload_tool(payload))
    if not binding:
        return None
    query = str(payload_input(payload).get(binding["query"], ""))
    if event in ("pretooluse", "beforemcpexecution"):
        key, data = find_match(entries, query, type_filter=binding["type"])
        decision = hook_pre(key, data, binding, platform) if key else None
        if decision is None and platform == "cursor":
            return {"permission": "allow"}
        return decision
    if event in ("posttooluse", "aftermcpexecution"):
        if not query:
            return None
        message = apply_post(entries, binding, query, payload_text(payload))
        if message:
            dump_cache(cache_path(config), entries)
        return hook_post_message(message, platform)
    return None


def script_path() -> Path:
    here = Path(__file__).resolve()
    linked = home() / ".claude" / "skills" / "alias" / "alias.py"
    try:
        if linked.exists() and linked.resolve() == here:
            return linked
    except OSError:
        pass
    return here


def hook_spec(config: dict | None) -> hooks_host.Spec:
    tools = config["tools"] if config else []
    claude = [hooks_host.Event("SessionStart", matcher=CLAUDE_SESSION_MATCHER)]
    for tool in tools:
        claude += [hooks_host.Event("PreToolUse", matcher=tool["tool"]),
                   hooks_host.Event("PostToolUse", matcher=tool["tool"])]
    return hooks_host.Spec(
        tag=TAG,
        state_dir=home() / ".alias",
        script=script_path(),
        events={
            "cursor": [hooks_host.Event(name) for name in ("sessionStart", "preToolUse", "postToolUse")],
            "claude": claude,
        },
    )


def check_platform(platform: str) -> None:
    if platform not in hooks_host.PLATFORMS:
        raise AliasError("platform must be claude or cursor")


def install_hooks(platform: str) -> dict:
    check_platform(platform)
    config = load_config()
    try:
        result = hooks_host.install(hook_spec(config), home(), platform)
    except hooks_host.HostError as exc:
        raise AliasError(str(exc)) from exc
    return {"ok": True, "platform": platform, "path": result["path"], "tools": len(config["tools"])}


def uninstall_hooks(platform: str) -> dict:
    check_platform(platform)
    try:
        return hooks_host.uninstall(hook_spec(None), home(), platform)
    except hooks_host.HostError as exc:
        raise AliasError(str(exc)) from exc


def hooks_status() -> dict:
    return hooks_host.status(hook_spec(None), home())


def emit(data, code: int = 0) -> int:
    if data is not None:
        sys.stdout.write(json.dumps(data) + "\n")
    return code


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: alias.py get|add|hook|hooks", file=sys.stderr)
        return 1
    command = argv[1]
    try:
        if command == "get":
            if len(argv) != 3:
                raise AliasError("usage: alias.py get <query>")
            return emit(cmd_get(argv[2]))
        if command == "add":
            if len(argv) < 4:
                raise AliasError("usage: alias.py add <type> <name> [field=value ...]")
            return emit(cmd_add(argv[2], argv[3], argv[4:]))
        if command == "hook":
            platform = "claude"
            if "--platform" in argv:
                platform = argv[argv.index("--platform") + 1]
            return emit(cmd_hook(platform) or {})
        if command == "hooks":
            action = argv[2] if len(argv) > 2 else ""
            if action == "status":
                return emit(hooks_status())
            if action == "install":
                if len(argv) != 4:
                    raise AliasError("usage: alias.py hooks install claude|cursor")
                return emit(install_hooks(argv[3]))
            if action == "uninstall":
                if len(argv) != 4:
                    raise AliasError("usage: alias.py hooks uninstall claude|cursor")
                return emit(uninstall_hooks(argv[3]))
            raise AliasError("usage: alias.py hooks install|uninstall|status")
    except AliasError as exc:
        return emit({"error": str(exc)}, 1)
    except json.JSONDecodeError as exc:
        return emit({"error": f"invalid JSON: {exc}"}, 1)
    print(f"unknown command: {command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
