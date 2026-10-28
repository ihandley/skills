#!/usr/bin/env python3
"""ticketer: deterministic ticket drafting, validation, and confirm gate.

Python never talks to a tracker. It validates a draft against team config and
tracker metadata, then emits a platform-neutral operation descriptor that the
agent executes with whatever tool it has. Every command prints one JSON object.
"""

from __future__ import annotations

import sys

# This guard must stay valid on old interpreters, so it runs before any 3.11+ import.
if sys.version_info < (3, 11):
    sys.stderr.write(
        "ticketer needs Python 3.11 or newer; found %s at %s.\n"
        "Run it under a newer interpreter, for example:\n"
        "  mise exec python@latest -- python3 %s ...\n"
        "  uv run --python 3.11 %s ...\n"
        % (sys.version.split()[0], sys.executable, sys.argv[0], sys.argv[0])
    )
    raise SystemExit(3)

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from adapters import ADAPTERS, get_adapter  # noqa: E402

SKILL_DIR = Path(__file__).resolve().parent
PLACEHOLDER = "REPLACE_ME"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
ID_RE = re.compile(r"^[0-9a-f]{12}$")
REMOTE_RE = re.compile(r"[:/]([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
OWNER_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MAPPINGS_FILE = "mappings.toml"
MAPPING_KEYS = {"path", "remote", "provider", "overrides"}

EXIT_REFUSED = 2
EXIT_CONFIG = 4
EXIT_STATE = 5

CONFIG_KEYS = {
    "tracker",
    "required",
    "required_by_type",
    "forbid_empty",
    "normalize_labels",
    "ai_disclosure",
    "enforce_templates",
    "template_dir",
    "require_metadata",
    "metadata_max_age_hours",
    "draft_max_age_hours",
    "defaults",
    "extra",
}
CREATE, UPDATE = "create", "update"


class Fail(Exception):
    def __init__(self, code, message, errors=None, **extra):
        super().__init__(message)
        self.code, self.message, self.errors, self.extra = code, message, errors or [], extra


def err(code, message, field=None):
    return {"code": code, "field": field, "message": message}


def emit(obj):
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def cache_dir():
    if os.environ.get("TICKETER_CACHE"):
        return Path(os.environ["TICKETER_CACHE"])
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "ticketer"


def config_home():
    return Path(os.environ.get("TICKETER_HOME") or Path.home() / ".config" / "ticketer")


def read_json_input(source):
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise Fail(EXIT_STATE, "input is not valid JSON: %s" % exc)


# ---------------------------------------------------------------- config

def resolve(args):
    """Locate team slug and config file. Pure filesystem lookup, no guessing."""
    cwd = Path(getattr(args, "cwd", None) or os.getcwd()).resolve()
    home = config_home()
    searched = []

    def walk_up(rel):
        for directory in [cwd, *cwd.parents]:
            candidate = directory / ".ticketer" / rel
            searched.append(str(candidate))
            if candidate.is_file():
                return candidate
        return None

    team = team_source = mapping = None
    overrides = {}
    if getattr(args, "team", None):
        team, team_source = args.team, "--team"
    else:
        pointer = walk_up("team")
        if pointer:
            team, team_source = pointer.read_text(encoding="utf-8").strip(), str(pointer)
        else:
            searched.append(str(home / MAPPINGS_FILE))
            mapping = match_mapping(load_mappings(home), cwd)
            if mapping:
                team, team_source = mapping["provider"], str(home / MAPPINGS_FILE)
                overrides = mapping.get("overrides", {})
    if team is not None and not SLUG_RE.match(team):
        raise Fail(EXIT_CONFIG, "team slug %r is invalid (lowercase letters, digits, - and _ only)" % team)

    config_path = None
    if getattr(args, "config", None):
        config_path = Path(args.config).expanduser().resolve()
        searched.append(str(config_path))
    elif team:
        config_path = walk_up("%s.toml" % team)
        if config_path is None:
            fallback = home / ("%s.toml" % team)
            searched.append(str(fallback))
            config_path = fallback if fallback.is_file() else None
    return {
        "python": sys.version.split()[0],
        "team": team,
        "team_source": team_source,
        "config_path": str(config_path) if config_path else None,
        "config_exists": bool(config_path and config_path.is_file()),
        "cwd": str(cwd),
        "mapping": mapping["_label"] if mapping else None,
        "overrides": overrides,
        "providers": list_providers(home),
        "searched": searched,
        "cache_dir": str(cache_dir()),
    }


def require_config(args):
    info = resolve(args)
    if not info["config_exists"]:
        raise Fail(
            EXIT_CONFIG,
            "no config found for this directory. Writes fail closed without one, and there is no default. "
            "Ask the user which provider config to use (existing: %s), or whether to create one with: "
            "ticketer.py init --provider <name> --tracker <jira|github>. Then save the choice with: "
            "ticketer.py map add --path <dir> --provider <name>" % (", ".join(info["providers"]) or "none"),
            searched=info["searched"],
            providers=info["providers"],
        )
    return info


def list_providers(home):
    if not home.is_dir():
        return []
    return sorted(p.stem for p in home.glob("*.toml") if p.name != MAPPINGS_FILE and SLUG_RE.match(p.stem))


def norm_path(value):
    return Path(value).expanduser().resolve()


def git_remote(cwd):
    try:
        proc = subprocess.run(["git", "-C", str(cwd), "remote", "get-url", "origin"],
                              capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    match = REMOTE_RE.search(proc.stdout.strip()) if proc.returncode == 0 else None
    return "%s/%s" % match.groups() if match else None


def load_mappings(home):
    path = home / MAPPINGS_FILE
    if not path.is_file():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise Fail(EXIT_CONFIG, "cannot read %s: %s" % (path, exc))
    problems = []
    unknown = sorted(set(data) - {"mapping"})
    if unknown:
        problems.append(err("unknown_mapping_key", "unknown top-level keys: %s" % ", ".join(unknown)))
    entries = data.get("mapping", [])
    for index, entry in enumerate(entries):
        where = "mapping #%d" % (index + 1)
        extra = sorted(set(entry) - MAPPING_KEYS)
        if extra:
            problems.append(err("unknown_mapping_key", "%s: unknown keys: %s" % (where, ", ".join(extra))))
        if not (isinstance(entry.get("provider"), str) and SLUG_RE.match(entry["provider"])):
            problems.append(err("bad_provider", "%s: provider must be a config name like jira or github" % where))
        for key in ("path", "remote"):
            if key in entry and not (isinstance(entry[key], str) and entry[key].strip()):
                problems.append(err("bad_type", "%s: %s must be a non-empty string" % (where, key)))
        if "path" not in entry and "remote" not in entry:
            problems.append(err("empty_mapping", "%s: needs a path, a remote, or both" % where))
        if "remote" in entry and isinstance(entry["remote"], str) and not OWNER_REPO_RE.match(entry["remote"]):
            problems.append(err("bad_remote", "%s: remote must look like owner/repo" % where))
        overrides = entry.get("overrides", {})
        if not isinstance(overrides, dict):
            problems.append(err("bad_type", "%s: overrides must be a table" % where))
        elif set(overrides) - (CONFIG_KEYS - {"tracker"}):
            bad = sorted(set(overrides) - (CONFIG_KEYS - {"tracker"}))
            problems.append(err("bad_override", "%s: cannot override %s" % (where, ", ".join(bad))))
    if problems:
        raise Fail(EXIT_CONFIG, "%s is invalid" % path, problems)
    return entries


def match_mapping(entries, cwd):
    """Longest path prefix wins. A remote-only entry matches only when no path entry does."""
    remote = git_remote(cwd) if any("remote" in e for e in entries) else None
    best, best_len = None, -1
    for entry in entries:
        length = 0
        if "path" in entry:
            root = norm_path(entry["path"])
            if not cwd.is_relative_to(root):
                continue
            length = len(root.parts)
        if "remote" in entry and (remote is None or entry["remote"].lower() != remote.lower()):
            continue
        if length > best_len:
            label = ", ".join("%s %s" % (k, entry[k]) for k in ("path", "remote") if k in entry)
            best, best_len = {**entry, "_label": label}, length
    return best


def deep_merge_config(data, overrides):
    for key, value in overrides.items():
        if key in ("defaults", "extra") and isinstance(value, dict):
            data[key] = {**data.get(key, {}), **value}
        else:
            data[key] = value


def load_config(path, overrides=None):
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise Fail(EXIT_CONFIG, "cannot read config %s: %s" % (path, exc))
    deep_merge_config(data, overrides or {})
    problems = []
    unknown = sorted(set(data) - CONFIG_KEYS)
    if unknown:
        problems.append(err("unknown_config_key", "unknown top-level keys: %s" % ", ".join(unknown)))
    tracker = data.get("tracker")
    if tracker not in ADAPTERS:
        problems.append(err("bad_tracker", "tracker must be one of: %s" % ", ".join(sorted(ADAPTERS)), "tracker"))
    for key in ("required", "forbid_empty"):
        value = data.get(key, [])
        if not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            problems.append(err("bad_type", "%s must be a list of strings" % key, key))
    by_type = data.get("required_by_type", {})
    if not (isinstance(by_type, dict) and all(
            isinstance(v, list) and all(isinstance(n, str) for n in v) for v in by_type.values())):
        problems.append(err("bad_type", "required_by_type must be a table of issue type to a list of strings", "required_by_type"))
    for key in ("normalize_labels", "enforce_templates", "require_metadata"):
        if key in data and not isinstance(data[key], bool):
            problems.append(err("bad_type", "%s must be true or false" % key, key))
    for key in ("metadata_max_age_hours", "draft_max_age_hours"):
        if key in data and (isinstance(data[key], bool) or not isinstance(data[key], (int, float)) or data[key] <= 0):
            problems.append(err("bad_type", "%s must be a positive number" % key, key))
    for key in ("ai_disclosure", "template_dir"):
        if key in data and not isinstance(data[key], str):
            problems.append(err("bad_type", "%s must be a string" % key, key))
    for table in ("defaults", "extra"):
        if table in data and not isinstance(data[table], dict):
            problems.append(err("bad_type", "[%s] must be a table" % table, table))
    if tracker in ADAPTERS and all(isinstance(data.get(t, {}), dict) for t in ("defaults", "extra")):
        adapter = get_adapter(tracker)
        for key in data.get("defaults", {}):
            if key not in adapter.DRAFT_KEYS or key in ("operation", "key"):
                problems.append(err("bad_default", "[defaults] key %r is not valid for %s" % (key, tracker), key))
        if data.get("extra") and not adapter.SUPPORTS_EXTRA:
            problems.append(err("bad_extra", "[extra] is not supported for %s" % tracker, "extra"))
        for table in ("defaults", "extra"):
            for key, value in data.get(table, {}).items():
                if value == PLACEHOLDER:
                    problems.append(err("placeholder", "%s.%s is still %s; set a real value" % (table, key, PLACEHOLDER), key))
    if problems:
        raise Fail(EXIT_CONFIG, "config %s is invalid" % path, problems)
    data.setdefault("required", ["summary"])
    data.setdefault("required_by_type", {})
    data.setdefault("forbid_empty", [])
    data.setdefault("enforce_templates", True)
    data.setdefault("require_metadata", False)
    data.setdefault("metadata_max_age_hours", 24)
    data.setdefault("draft_max_age_hours", 4)
    data.setdefault("defaults", {})
    data.setdefault("extra", {})
    data["_path"] = str(path)
    data["_overrides"] = overrides or {}
    data["_sha"] = hashlib.sha256(path.read_bytes() + canonical(overrides or {}).encode()).hexdigest()
    return data


# ---------------------------------------------------------------- templates

def sections(text):
    out, current = {}, None
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            current = match.group(1).strip().casefold()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in out.items()}


def find_template(issue_type, config):
    if not issue_type:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", issue_type.casefold()).strip("-")
    dirs = []
    if config.get("template_dir"):
        dirs.append(Path(config["_path"]).parent / config["template_dir"])
    dirs.append(SKILL_DIR / "templates")
    for directory in dirs:
        candidate = directory / ("%s.md" % slug)
        if candidate.is_file():
            return candidate
    return None


def _norm_line(line):
    return re.sub(r"^[-*]\s*(\[[ xX]\]\s*)?", "", line.strip()).strip().casefold()


def check_description(draft, config):
    problems = []
    description = draft.get("description") or ""
    template = find_template(draft.get("issue_type"), config)
    parsed = sections(description)
    if template and config["enforce_templates"]:
        for heading in sections(template.read_text(encoding="utf-8")):
            if not parsed.get(heading):
                problems.append(err("empty_section", "description needs a non-empty '## %s' section (template %s)" % (heading, template.name), "description"))
    ac_key = next((k for k in parsed if k.startswith("acceptance criteria")), None)
    if ac_key:
        ac_lines = {_norm_line(l) for l in parsed[ac_key].splitlines() if len(_norm_line(l)) >= 20}
        for name, body in parsed.items():
            if name == ac_key:
                continue
            for line in body.splitlines():
                if _norm_line(line) in ac_lines:
                    problems.append(err("duplicate_content", "line repeated in '%s' and acceptance criteria: %r" % (name, line.strip()[:60]), "description"))
    return problems


# ---------------------------------------------------------------- drafts

def normalize_label(label):
    return re.sub(r"-{2,}", "-", re.sub(r"[\s_]+", "-", label.strip().casefold()))


def build_draft(raw, adapter, config):
    if not isinstance(raw, dict):
        raise Fail(EXIT_REFUSED, "draft input must be a JSON object")
    unknown = sorted(set(raw) - adapter.DRAFT_KEYS)
    if unknown:
        raise Fail(EXIT_REFUSED, "unknown draft keys for %s: %s" % (adapter.NAME, ", ".join(unknown)))
    problems = []
    for key, value in raw.items():
        kind = adapter.FIELDS.get(key)
        if kind == "str" and not isinstance(value, str):
            problems.append(err("bad_type", "%s must be a string" % key, key))
        if kind == "list" and not (isinstance(value, list) and all(isinstance(v, str) for v in value)):
            problems.append(err("bad_type", "%s must be a list of strings" % key, key))
        if kind == "object" and not isinstance(value, dict):
            problems.append(err("bad_type", "fields must be an object", key))
    if problems:
        raise Fail(EXIT_REFUSED, "draft has wrong types", problems)

    operation = raw.get("operation", CREATE)
    if operation not in (CREATE, UPDATE):
        raise Fail(EXIT_REFUSED, "operation must be 'create' or 'update'")
    defaults = config["defaults"]
    draft = {}
    if operation == CREATE:
        for key, value in defaults.items():
            draft[key] = list(value) if isinstance(value, list) else value
        for key, value in raw.items():
            if key in adapter.MERGE_LIST_KEYS and key in draft:
                draft[key] = list(dict.fromkeys(list(draft[key]) + list(value)))
            else:
                draft[key] = value
        if config["extra"]:
            draft["fields"] = {**config["extra"], **raw.get("fields", {})}
    else:
        for key in adapter.IDENT_KEYS:
            if key in defaults:
                draft[key] = defaults[key]
        draft.update(raw)
    draft["operation"] = operation

    notes = []
    for key in list(draft):
        if isinstance(draft[key], str):
            draft[key] = draft[key].replace("\r\n", "\n").strip()
    if config.get("normalize_labels", adapter.NORMALIZE_LABELS) and draft.get("labels"):
        fixed = list(dict.fromkeys(normalize_label(l) for l in draft["labels"] if l.strip()))
        if fixed != draft["labels"]:
            notes.append("labels normalized: %s -> %s" % (draft["labels"], fixed))
        draft["labels"] = fixed
    disclosure = config.get("ai_disclosure", "").strip()
    if operation == CREATE and disclosure and draft.get("description") and not draft["description"].startswith(disclosure):
        draft["description"] = disclosure + "\n\n" + draft["description"]
    return {k: v for k, v in draft.items() if v is not None}, notes


def validate_draft(draft, config, adapter, metadata):
    problems, warnings, needs = [], [], []
    operation = draft["operation"]
    if operation == CREATE:
        if "summary" not in config["required"]:
            config = {**config, "required": ["summary"] + list(config["required"])}
        issue_type = (draft.get("issue_type") or "").casefold()
        extra_required = [n for t, names in config["required_by_type"].items() if t.casefold() == issue_type for n in names]
        for name in dict.fromkeys(list(config["required"]) + extra_required):
            value = draft.get("fields", {}).get(name) if name.startswith("customfield_") else draft.get(name)
            if is_empty(value):
                problems.append(err("required_missing", "required field %r is missing or empty" % name, name))
        problems += check_description(draft, config)
    else:
        if is_empty(draft.get("key")):
            problems.append(err("required_missing", "update needs 'key'", "key"))
        changes = set(draft) - {"operation", "key"} - set(adapter.IDENT_KEYS)
        if not changes:
            problems.append(err("no_changes", "update changes nothing", None))
    for name in config["forbid_empty"]:
        value = draft.get("fields", {}).get(name) if name.startswith("customfield_") else draft.get(name)
        if (operation == CREATE or name in draft) and is_empty(value):
            problems.append(err("forbidden_empty", "%r may not be empty" % name, name))
    stale_or_missing = metadata is None
    if stale_or_missing:
        scope = adapter.scope(draft)
        needs = adapter.metadata_needs(draft, scope)
        if config["require_metadata"]:
            problems.append(err("metadata_missing", "tracker metadata is missing or stale; fetch it and run 'metadata store' (see needs)", None))
        else:
            warnings.append("tracker metadata not checked (none cached)")
    problems += adapter.validate(draft, config, metadata)
    return problems, warnings, needs


def render(draft, draft_id, adapter):
    lines = ["TICKET DRAFT %s  (%s on %s)" % (draft_id, draft["operation"], adapter.NAME)]
    for key in adapter.DISPLAY_ORDER:
        if key in draft:
            value = draft[key]
            lines.append("%s: %s" % (key, ", ".join(value) if isinstance(value, list) else value))
    for key, value in sorted(draft.get("fields", {}).items()):
        lines.append("%s: %s" % (key, json.dumps(value, ensure_ascii=False)))
    if draft.get("description"):
        lines += ["", "description:", draft["description"]]
    return "\n".join(lines)


def draft_path(draft_id):
    if not ID_RE.match(draft_id or ""):
        raise Fail(EXIT_STATE, "draft id %r is malformed" % draft_id)
    return cache_dir() / "drafts" / ("%s.json" % draft_id)


def load_record(draft_id):
    path = draft_path(draft_id)
    if not path.is_file():
        raise Fail(EXIT_STATE, "no draft %s. Run 'draft' first." % draft_id)
    return json.loads(path.read_text(encoding="utf-8"))


def save_record(record):
    path = draft_path(record["id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------- metadata

def metadata_path(tracker, scope):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "__", scope or "none")
    return cache_dir() / "metadata" / ("%s-%s.json" % (tracker, safe))


def load_metadata(tracker, scope, config):
    path = metadata_path(tracker, scope)
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    age_hours = (time.time() - data.get("fetched_at", 0)) / 3600
    return data if age_hours <= config["metadata_max_age_hours"] else None


# ---------------------------------------------------------------- commands

def cmd_locate(args):
    info = resolve(args)
    info["ok"] = True
    return info, 0


def cmd_init(args):
    adapter = get_adapter(args.tracker)
    provider = args.provider or args.tracker
    if not SLUG_RE.match(provider):
        raise Fail(EXIT_CONFIG, "provider name must match %s" % SLUG_RE.pattern)
    repo_scope = args.scope == "repo"
    base = (Path(os.getcwd()) / ".ticketer") if repo_scope else config_home()
    target = base / ("%s.toml" % provider)
    if target.exists() and not args.force:
        raise Fail(EXIT_STATE, "%s already exists; pass --force to overwrite" % target)
    base.mkdir(parents=True, exist_ok=True)
    target.write_text(adapter.CONFIG_TEMPLATE, encoding="utf-8")
    pointer = base / "team"
    wrote_pointer = repo_scope and (not pointer.exists() or args.force)
    if wrote_pointer:
        pointer.write_text(provider + "\n", encoding="utf-8")
    if repo_scope:
        follow = "Commit .ticketer/%s.toml so teammates share it." % provider
    else:
        follow = "Then map a directory to it: ticketer.py map add --path <dir> --provider %s." % provider
    return {
        "ok": True,
        "config_path": str(target),
        "team_pointer": str(pointer) if wrote_pointer else None,
        "next": "Replace every %s value in the config, then ask the user to review it. %s" % (PLACEHOLDER, follow),
    }, 0


def split_mapping_blocks(text):
    head, blocks = [], []
    for line in text.splitlines(keepends=True):
        if line.strip() == "[[mapping]]":
            blocks.append([line])
        elif blocks:
            blocks[-1].append(line)
        else:
            head.append(line)
    return "".join(head), ["".join(block) for block in blocks]


def mapping_block(path, remote, provider, old_block=""):
    lines = ["[[mapping]]\n"]
    if path:
        lines.append("path = %s\n" % json.dumps(path))
    if remote:
        lines.append("remote = %s\n" % json.dumps(remote))
    lines.append("provider = %s\n" % json.dumps(provider))
    kept = re.search(r"^\s*\[mapping\.", old_block, re.MULTILINE)
    return "".join(lines) + (old_block[kept.start():] if kept else "")


def write_atomic(path, text):
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".mappings-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cmd_map_add(args):
    home = config_home()
    if not SLUG_RE.match(args.provider):
        raise Fail(EXIT_CONFIG, "provider name must match %s" % SLUG_RE.pattern)
    if not (args.path or args.remote):
        raise Fail(EXIT_CONFIG, "give --path, --remote, or both")
    if args.remote and not OWNER_REPO_RE.match(args.remote):
        raise Fail(EXIT_CONFIG, "--remote must look like owner/repo")
    if not (home / ("%s.toml" % args.provider)).is_file():
        raise Fail(EXIT_STATE, "no config named %s in %s. Create it first: ticketer.py init --provider %s --tracker <jira|github>"
                   % (args.provider, home, args.provider))
    path = str(norm_path(args.path)) if args.path else None
    target = home / MAPPINGS_FILE
    entries = load_mappings(home)
    key = (path, args.remote.lower() if args.remote else None)
    same = [i for i, e in enumerate(entries)
            if (str(norm_path(e["path"])) if "path" in e else None, e["remote"].lower() if "remote" in e else None) == key]
    text = target.read_text(encoding="utf-8") if target.is_file() else ""
    head, blocks = split_mapping_blocks(text)
    if len(blocks) != len(entries):
        raise Fail(EXIT_STATE, "cannot edit %s safely. Edit it by hand." % target)
    if same and not args.force:
        raise Fail(EXIT_STATE, "%s already maps %s; pass --force to replace it"
                   % (target, " + ".join(v for v in (path, args.remote) if v)))
    if same:
        blocks[same[0]] = mapping_block(path, args.remote, args.provider, blocks[same[0]])
    else:
        if blocks and not blocks[-1].endswith("\n\n"):
            blocks[-1] = blocks[-1].rstrip("\n") + "\n\n"
        blocks.append(mapping_block(path, args.remote, args.provider))
    home.mkdir(parents=True, exist_ok=True)
    write_atomic(target, head + "".join(blocks))
    load_mappings(home)
    return {"ok": True, "mappings_path": str(target), "replaced": bool(same),
            "entry": {"path": path, "remote": args.remote, "provider": args.provider}}, 0


def cmd_metadata_store(args):
    adapter = get_adapter(args.tracker)
    raw = read_json_input(args.input)
    path = metadata_path(args.tracker, args.scope)
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    try:
        if args.kind not in adapter.METADATA_KINDS:
            raise ValueError("%s has no metadata kind %r; supported: %s" % (adapter.NAME, args.kind, ", ".join(adapter.METADATA_KINDS)))
        adapter.store_metadata(data, args.kind, raw, args.issue_type)
    except ValueError as exc:
        raise Fail(EXIT_REFUSED, str(exc))
    data["fetched_at"] = time.time()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "path": str(path), "kind": args.kind, "scope": args.scope}, 0


def cmd_draft(args):
    info = require_config(args)
    config = load_config(info["config_path"], info["overrides"])
    adapter = get_adapter(config["tracker"])
    raw = read_json_input("-")
    draft, notes = build_draft(raw, adapter, config)
    metadata = load_metadata(adapter.NAME, adapter.scope(draft), config)
    problems, warnings, needs = validate_draft(draft, config, adapter, metadata)
    if problems:
        return {"ok": False, "error": "draft is invalid; fix the errors and run draft again",
                "errors": problems, "needs": needs, "notes": notes}, EXIT_REFUSED
    nonce = str(time.time()) if args.allow_duplicate else ""
    draft_id = hashlib.sha256(canonical({"t": adapter.NAME, "d": draft, "n": nonce}).encode()).hexdigest()[:12]
    existing = draft_path(draft_id)
    if existing.is_file():
        status = json.loads(existing.read_text(encoding="utf-8")).get("status")
        if status != "drafted":
            raise Fail(EXIT_REFUSED,
                       "an identical draft was already %s. Use --allow-duplicate only if the user wants a second ticket." % status)
    save_record({"id": draft_id, "status": "drafted", "created_at": time.time(), "tracker": adapter.NAME,
                 "config_path": config["_path"], "resolve": {"cwd": info["cwd"], "team": getattr(args, "team", None), "config": getattr(args, "config", None)},
                 "config_sha": config["_sha"], "draft": draft})
    return {
        "ok": True, "id": draft_id, "render": render(draft, draft_id, adapter),
        "warnings": warnings, "notes": notes, "needs": needs,
        "ask": "Show 'render' to the user verbatim, then ask: Proceed? (yes / no / edit). "
               "Only on 'yes': ticketer.py submit --draft %s --confirm %s" % (draft_id, draft_id),
    }, 0


def cmd_submit(args):
    record = load_record(args.draft)
    if args.confirm != record["id"]:
        raise Fail(EXIT_REFUSED, "confirmation token does not match the draft id; the user has not confirmed this draft")
    if record["status"] != "drafted" and not args.resend:
        raise Fail(EXIT_REFUSED, "draft is already %s; refusing to emit it twice (--resend overrides)" % record["status"])
    if "resolve" not in record:
        raise Fail(EXIT_REFUSED, "draft predates the current resolver; run draft again")
    current = resolve(argparse.Namespace(**record["resolve"]))
    config = load_config(record["config_path"], current["overrides"])
    if config["_sha"] != record["config_sha"]:
        raise Fail(EXIT_REFUSED, "team config changed since the draft; run draft again")
    if time.time() - record["created_at"] > config["draft_max_age_hours"] * 3600:
        raise Fail(EXIT_REFUSED, "draft is older than %s hours; run draft again" % config["draft_max_age_hours"])
    adapter = get_adapter(record["tracker"])
    draft = record["draft"]
    metadata = load_metadata(adapter.NAME, adapter.scope(draft), config)
    problems, warnings, needs = validate_draft(draft, config, adapter, metadata)
    if problems:
        return {"ok": False, "error": "draft no longer validates", "errors": problems, "needs": needs}, EXIT_REFUSED
    body_path = None
    if draft.get("description"):
        body_path = cache_dir() / "bodies" / ("%s.md" % record["id"])
        body_path.parent.mkdir(parents=True, exist_ok=True)
        body_path.write_text(draft["description"] + "\n", encoding="utf-8")
    descriptor = adapter.build(draft, str(body_path) if body_path else None)
    record["status"] = "emitted"
    record["emitted_at"] = time.time()
    save_record(record)
    return {
        "ok": True, "id": record["id"], "descriptor": descriptor,
        "readback": adapter.readback(draft),
        "next": "Execute 'descriptor' with the matching tool (references/tool-map.md). Then run the 'readback' "
                "operation, substituting the placeholder, and pipe its JSON to: ticketer.py verify --draft %s --result -" % record["id"],
        "warnings": warnings,
    }, 0


def cmd_verify(args):
    record = load_record(args.draft)
    if record["status"] not in ("emitted", "verified"):
        raise Fail(EXIT_STATE, "draft is %s; submit it first" % record["status"])
    adapter = get_adapter(record["tracker"])
    result = read_json_input(args.result)
    mismatches, unverifiable, ref = adapter.diff(record["draft"], result)
    ok = not mismatches
    if ok:
        record["status"], record["ref"] = "verified", ref
        save_record(record)
    return {"ok": ok, "ref": ref, "mismatches": mismatches, "unverifiable": unverifiable}, 0 if ok else EXIT_REFUSED


def cmd_find_parent(args):
    info = require_config(args)
    config = load_config(info["config_path"], info["overrides"])
    adapter = get_adapter(config["tracker"])
    descriptor = adapter.find_parent(args.query, config)
    if descriptor is None:
        raise Fail(EXIT_REFUSED, "%s does not support parent search" % adapter.NAME)
    return {"ok": True, "descriptor": descriptor}, 0


def parser():
    top = argparse.ArgumentParser(prog="ticketer.py", description=__doc__)
    sub = top.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--team")
        p.add_argument("--config")
        p.add_argument("--cwd", help=argparse.SUPPRESS)

    p = sub.add_parser("locate", help="resolve team slug and config path")
    common(p)
    p.set_defaults(fn=cmd_locate)

    p = sub.add_parser("init", help="write a starter provider config")
    p.add_argument("--provider", "--team", dest="provider", help="config name; defaults to the tracker name")
    p.add_argument("--tracker", required=True, choices=sorted(ADAPTERS))
    p.add_argument("--scope", choices=["user", "repo"], default="user")
    p.add_argument("--force", action="store_true")
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("map", help="map a directory or git remote to a provider config")
    msub = p.add_subparsers(dest="map_command", required=True)
    s_add = msub.add_parser("add")
    s_add.add_argument("--path")
    s_add.add_argument("--remote", help="owner/repo")
    s_add.add_argument("--provider", required=True)
    s_add.add_argument("--force", action="store_true")
    s_add.set_defaults(fn=cmd_map_add)

    p = sub.add_parser("metadata", help="cache tracker metadata the agent fetched")
    msub = p.add_subparsers(dest="metadata_command", required=True)
    s = msub.add_parser("store")
    s.add_argument("--tracker", required=True, choices=sorted(ADAPTERS))
    s.add_argument("--scope", required=True, help="Jira project key or GitHub owner/repo")
    s.add_argument("--kind", required=True, choices=sorted({k for a in ADAPTERS.values() for k in a.METADATA_KINDS}))
    s.add_argument("--issue-type")
    s.add_argument("--input", default="-")
    s.set_defaults(fn=cmd_metadata_store)

    p = sub.add_parser("draft", help="read a draft as JSON on stdin; validate, render, hash")
    common(p)
    p.add_argument("--allow-duplicate", action="store_true")
    p.set_defaults(fn=cmd_draft)

    p = sub.add_parser("submit", help="emit the operation descriptor once the user confirmed")
    p.add_argument("--draft", required=True)
    p.add_argument("--confirm", required=True)
    p.add_argument("--resend", action="store_true")
    p.set_defaults(fn=cmd_submit)

    p = sub.add_parser("verify", help="diff the tracker's read-back against the draft")
    p.add_argument("--draft", required=True)
    p.add_argument("--result", default="-")
    p.set_defaults(fn=cmd_verify)

    p = sub.add_parser("find-parent", help="emit a search for an existing parent epic")
    common(p)
    p.add_argument("--query", required=True)
    p.set_defaults(fn=cmd_find_parent)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        result, code = args.fn(args)
    except Fail as exc:
        result = {"ok": False, "error": exc.message, "errors": exc.errors, **exc.extra}
        code = exc.code
    emit(result)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
