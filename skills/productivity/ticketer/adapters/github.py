"""GitHub Issues adapter. Payloads map onto `gh issue` and the GitHub MCP issue tools."""

from __future__ import annotations

import re

NAME = "github"
FIELDS = {
    "operation": "str", "key": "str", "summary": "str", "description": "str", "labels": "list",
    "assignees": "list", "milestone": "str", "repo": "str", "issue_type": "str",
}
DRAFT_KEYS = set(FIELDS)
MERGE_LIST_KEYS = {"labels"}
DISPLAY_ORDER = ("key", "repo", "issue_type", "summary", "assignees", "milestone", "labels")
METADATA_KINDS = ("labels",)
IDENT_KEYS = ("repo",)
SUPPORTS_EXTRA = False
NORMALIZE_LABELS = False

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
NUMBER_RE = re.compile(r"^[0-9]+$")

CONFIG_TEMPLATE = '''# ticketer team config (GitHub Issues). Replace every REPLACE_ME, then review with your team.
tracker = "github"

# Fields a create must carry.
required = ["summary", "description", "labels"]

# Fields that may never be empty, on create or when an update touches them.
forbid_empty = ["labels"]

# Reject a create when a description lacks a section its issue-type template requires.
enforce_templates = true

# Set to a fixed line to prepend to created descriptions, or leave empty.
ai_disclosure = ""

# Refuse to validate until the repo's labels have been fetched and stored.
require_metadata = false

[defaults]
repo = "REPLACE_ME"           # owner/name
# labels = ["needs-triage"]
# assignees = ["octocat"]
'''


def scope(draft):
    return draft.get("repo") or ""


def metadata_needs(draft, scope_value):
    repo = scope_value or "<owner/repo>"
    return [{
        "kind": "labels", "operation": "github.list_labels", "payload": {"repo": repo},
        "then": "ticketer.py metadata store --tracker github --scope %s --kind labels --input -" % repo,
    }]


def find_parent(query, config):
    """GitHub issues have no parent search."""
    return None


def store_metadata(data, kind, raw, issue_type):
    if kind != "labels":
        raise ValueError("github has no metadata kind %r" % kind)
    items = raw if isinstance(raw, list) else (raw.get("labels") or raw.get("items") or [] if isinstance(raw, dict) else [])
    data["labels"] = sorted({(i.get("name") if isinstance(i, dict) else str(i)) for i in items if i})


def _err(code, message, field=None):
    return {"code": code, "field": field, "message": message}


def validate(draft, config, metadata):
    problems = []
    if not draft.get("repo"):
        problems.append(_err("required_missing", "github needs 'repo' (owner/name)", "repo"))
    elif not REPO_RE.match(draft["repo"]):
        problems.append(_err("bad_format", "repo %r must look like owner/name" % draft["repo"], "repo"))
    if draft["operation"] == "update" and draft.get("key") and not NUMBER_RE.match(draft["key"]):
        problems.append(_err("bad_format", "key %r must be an issue number" % draft["key"], "key"))
    if metadata and metadata.get("labels") is not None:
        known = {l.casefold() for l in metadata["labels"]}
        for label in draft.get("labels", []):
            if label.casefold() not in known:
                problems.append(_err("unknown_label", "label %r does not exist in %s; create it or pick one of: %s" % (label, draft.get("repo"), ", ".join(metadata["labels"]) or "(none)"), "labels"))
    return problems


def build(draft, body_path):
    if draft["operation"] == "create":
        payload = {"repo": draft["repo"], "title": draft["summary"]}
        if draft.get("description"):
            payload["body"] = draft["description"]
            payload["body_file"] = body_path
        for key in ("labels", "assignees", "milestone"):
            if draft.get(key):
                payload[key] = draft[key]
        if draft.get("issue_type"):
            payload["type"] = draft["issue_type"]
        return {"operation": "github.create_issue", "payload": payload}
    payload = {"repo": draft["repo"], "number": int(draft["key"])}
    if "summary" in draft:
        payload["title"] = draft["summary"]
    if "description" in draft:
        payload["body"] = draft["description"]
        payload["body_file"] = body_path
    for key in ("labels", "assignees", "milestone"):
        if key in draft:
            payload[key] = draft[key]
    if "issue_type" in draft:
        payload["type"] = draft["issue_type"]
    return {"operation": "github.edit_issue", "payload": payload,
            "note": "labels and assignees replace the whole list; a milestone is set by title or number"}


def readback(draft):
    number = draft.get("key") or "<number returned by create>"
    return {"operation": "github.get_issue", "payload": {"repo": draft["repo"], "number": number}}


def _names(items, field):
    out = []
    for i in items or []:
        out.append(i.get(field) if isinstance(i, dict) else str(i))
    return sorted(x.casefold() for x in out if x)


def diff(draft, result):
    mismatches, unverifiable = [], []
    result = result if isinstance(result, dict) else {}

    def check(name, expected, got):
        if expected != got:
            mismatches.append({"field": name, "expected": expected, "actual": got})

    if "summary" in draft:
        check("summary", draft["summary"], (result.get("title") or "").strip())
    if "description" in draft:
        check("description", draft["description"].strip(), (result.get("body") or "").replace("\r\n", "\n").strip())
    if "labels" in draft:
        check("labels", sorted(l.casefold() for l in draft["labels"]), _names(result.get("labels"), "name"))
    if "assignees" in draft:
        check("assignees", sorted(a.casefold() for a in draft["assignees"]), _names(result.get("assignees"), "login"))
    if "milestone" in draft:
        milestone = result.get("milestone")
        got = milestone.get("title") if isinstance(milestone, dict) else milestone
        check("milestone", draft["milestone"], got)
    if "issue_type" in draft:
        unverifiable.append("issue_type (not returned by every GitHub tool)")
    number = result.get("number")
    ref = result.get("html_url") or (str(number) if number is not None else draft.get("key"))
    return mismatches, unverifiable, ref
