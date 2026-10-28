"""Jira adapter. Payloads follow the Atlassian createJiraIssue / editJiraIssue shape."""

from __future__ import annotations

import re

NAME = "jira"
FIELDS = {
    "operation": "str", "key": "str", "summary": "str", "description": "str", "issue_type": "str",
    "priority": "str", "parent": "str", "assignee": "str", "labels": "list", "components": "list",
    "project_key": "str", "cloud_id": "str", "fields": "object",
}
DRAFT_KEYS = set(FIELDS)
MERGE_LIST_KEYS = {"labels", "components"}
DISPLAY_ORDER = ("key", "project_key", "issue_type", "summary", "priority", "parent", "assignee",
                 "labels", "components")
METADATA_KINDS = ("issue-types", "fields")
IDENT_KEYS = ("project_key", "cloud_id")
SUPPORTS_EXTRA = True
NORMALIZE_LABELS = True

KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-[0-9]+$")
PROJECT_RE = re.compile(r"^[A-Z][A-Z0-9_]+$")
SUBTASK_TYPES = {"sub-task", "subtask"}
SKIP_META = {"project", "issuetype", "reporter", "attachment", "issuelinks"}
FIELD_TO_DRAFT = {
    "summary": "summary", "description": "description", "priority": "priority",
    "labels": "labels", "components": "components", "assignee": "assignee", "parent": "parent",
}

CONFIG_TEMPLATE = '''# ticketer team config (Jira). Replace every REPLACE_ME, then review with your team.
tracker = "jira"

# Fields a create must carry. Name a customfield_NNNNN to require it in the draft's "fields".
required = ["summary", "description", "issue_type", "labels"]

# Fields that may never be empty, on create or when an update touches them.
forbid_empty = ["labels"]

# Lowercase kebab-case labels (Jira labels are case-sensitive and cannot contain spaces).
normalize_labels = true

# Reject a create when a description lacks a section its issue-type template requires.
enforce_templates = true

# Set to a fixed line to prepend to created descriptions, or leave empty.
ai_disclosure = ""

# Refuse to validate until tracker metadata has been fetched and stored.
require_metadata = false

[defaults]
cloud_id = "REPLACE_ME"       # Atlassian cloud id or site hostname
project_key = "REPLACE_ME"    # e.g. "PROJ"
# components = ["Backend"]
# labels = ["team-label"]
# priority = "Medium"

[extra]
# Team-specific fields, sent as additional_fields on create. Take ids from the tracker's field metadata.
# customfield_10001 = "REPLACE_ME"
'''


def scope(draft):
    return draft.get("project_key") or ""


def metadata_needs(draft, scope_value):
    project = scope_value or "<project_key>"
    cloud = draft.get("cloud_id") or "<cloud_id>"
    needs = [{
        "kind": "issue-types", "operation": "jira.get_project_issue_types",
        "payload": {"cloudId": cloud, "projectIdOrKey": project},
        "then": "ticketer.py metadata store --tracker jira --scope %s --kind issue-types --input -" % project,
    }]
    if draft.get("operation") == "create" and draft.get("issue_type"):
        needs.append({
            "kind": "fields", "operation": "jira.get_create_fields",
            "payload": {"cloudId": cloud, "projectIdOrKey": project, "issueTypeId": "<id of '%s' from issue-types>" % draft["issue_type"]},
            "then": "ticketer.py metadata store --tracker jira --scope %s --kind fields --issue-type '%s' --input -" % (project, draft["issue_type"]),
        })
    return needs


def _items(raw, *keys):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in keys:
            value = raw.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return [{**v, "fieldId": k} for k, v in value.items() if isinstance(v, dict)]
    return []


def _scalar(value):
    if isinstance(value, dict):
        for key in ("value", "name", "id"):
            if value.get(key) is not None:
                return str(value[key])
        return None
    if isinstance(value, list):
        return [_scalar(v) for v in value]
    return None if value is None else str(value)


def store_metadata(data, kind, raw, issue_type):
    if kind == "issue-types":
        data["issue_types"] = sorted({i["name"] for i in _items(raw, "issueTypes", "values") if isinstance(i, dict) and i.get("name")})
    elif kind == "fields":
        if not issue_type:
            raise ValueError("--issue-type is required with --kind fields")
        fields = {}
        for item in _items(raw, "fields", "values"):
            if not isinstance(item, dict):
                continue
            fid = item.get("fieldId") or item.get("key")
            if not fid:
                continue
            allowed = [s for s in (_scalar(a) for a in item.get("allowedValues", [])) if s]
            ids = [str(a["id"]) for a in item.get("allowedValues", []) if isinstance(a, dict) and a.get("id") is not None]
            fields[fid] = {"required": bool(item.get("required")), "name": item.get("name", fid), "allowed": allowed, "allowed_ids": ids}
        data.setdefault("fields", {})[issue_type] = fields
    else:
        raise ValueError("jira has no metadata kind %r" % kind)


def _err(code, message, field=None):
    return {"code": code, "field": field, "message": message}


def validate(draft, config, metadata):
    problems = []
    operation = draft["operation"]
    if operation == "create":
        for name in ("cloud_id", "project_key", "issue_type"):
            if not draft.get(name):
                problems.append(_err("required_missing", "jira create needs %r" % name, name))
    else:
        if not draft.get("cloud_id"):
            problems.append(_err("required_missing", "jira update needs 'cloud_id'", "cloud_id"))
        if draft.get("key") and not KEY_RE.match(draft["key"]):
            problems.append(_err("bad_format", "key %r is not an issue key like PROJ-123" % draft["key"], "key"))
    if draft.get("project_key") and not PROJECT_RE.match(draft["project_key"]):
        problems.append(_err("bad_format", "project_key %r must be uppercase letters, digits, _" % draft["project_key"], "project_key"))
    if draft.get("parent") and not KEY_RE.match(draft["parent"]):
        problems.append(_err("bad_format", "parent %r is not an issue key like PROJ-123" % draft["parent"], "parent"))
    if (draft.get("issue_type") or "").casefold() in SUBTASK_TYPES and not draft.get("parent"):
        problems.append(_err("required_missing", "a sub-task needs 'parent'", "parent"))
    for label in draft.get("labels", []):
        if re.search(r"\s", label):
            problems.append(_err("bad_format", "label %r contains whitespace; Jira rejects it" % label, "labels"))
    for fid in draft.get("fields", {}):
        if fid in FIELD_TO_DRAFT:
            problems.append(_err("misplaced_field", "%r is a standard field; use the top-level draft key" % fid, fid))
    if not metadata:
        return problems

    types = metadata.get("issue_types")
    if types and draft.get("issue_type") and draft["issue_type"] not in types:
        problems.append(_err("unknown_issue_type", "issue type %r not in this project; available: %s" % (draft["issue_type"], ", ".join(types)), "issue_type"))
    meta_fields = (metadata.get("fields") or {}).get(draft.get("issue_type") or "")
    if meta_fields:
        for fid, info in meta_fields.items():
            if fid in SKIP_META:
                continue
            draft_key = FIELD_TO_DRAFT.get(fid)
            value = draft.get(draft_key) if draft_key else draft.get("fields", {}).get(fid)
            if operation == "create" and info["required"] and value in (None, "", [], {}):
                problems.append(_err("tracker_required", "tracker requires %r (%s) for %s" % (fid, info["name"], draft["issue_type"]), fid))
            if value not in (None, "", [], {}) and info["allowed"]:
                ids = info.get("allowed_ids", [])
                for entry in value if isinstance(value, list) else [value]:
                    by_id = isinstance(entry, dict) and entry.get("value") is None and entry.get("name") is None and entry.get("id") is not None
                    item = str(entry["id"]) if by_id else _scalar(entry)
                    if item not in (ids if by_id else info["allowed"]):
                        problems.append(_err("bad_value", "%r is not allowed for %s; allowed: %s" % (item, info["name"], ", ".join(info["allowed"])), fid))
    return problems


def build(draft, body_path):
    cloud = draft["cloud_id"]
    if draft["operation"] == "create":
        extra = {}
        if draft.get("labels"):
            extra["labels"] = draft["labels"]
        if draft.get("priority"):
            extra["priority"] = {"name": draft["priority"]}
        if draft.get("components"):
            extra["components"] = [{"name": c} for c in draft["components"]]
        extra.update(draft.get("fields", {}))
        payload = {
            "cloudId": cloud, "projectKey": draft["project_key"], "issueTypeName": draft["issue_type"],
            "summary": draft["summary"], "contentFormat": "markdown",
        }
        if draft.get("description"):
            payload["description"] = draft["description"]
        if draft.get("parent"):
            payload["parent"] = draft["parent"]
        if draft.get("assignee"):
            payload["assignee_account_id"] = draft["assignee"]
        if extra:
            payload["additional_fields"] = extra
        return {"operation": "jira.create_issue", "payload": payload}
    fields = {}
    if "summary" in draft:
        fields["summary"] = draft["summary"]
    if "description" in draft:
        fields["description"] = draft["description"]
    if "labels" in draft:
        fields["labels"] = draft["labels"]
    if "priority" in draft:
        fields["priority"] = {"name": draft["priority"]}
    if "components" in draft:
        fields["components"] = [{"name": c} for c in draft["components"]]
    if "assignee" in draft:
        fields["assignee"] = {"accountId": draft["assignee"]}
    if "parent" in draft:
        fields["parent"] = {"key": draft["parent"]}
    fields.update(draft.get("fields", {}))
    return {"operation": "jira.edit_issue",
            "payload": {"cloudId": cloud, "issueIdOrKey": draft["key"], "fields": fields, "contentFormat": "markdown"},
            "note": "labels and components replace the whole list; description and summary replace the old value"}


def readback(draft):
    key = draft.get("key") or "<KEY returned by create>"
    return {"operation": "jira.get_issue",
            "payload": {"cloudId": draft["cloud_id"], "issueIdOrKey": key,
                        "fields": ["summary", "description", "issuetype", "priority", "labels", "components", "parent", "assignee"]}}


def find_parent(query, config):
    defaults = config["defaults"]
    project = defaults.get("project_key", "<project_key>")
    safe = query.replace("\\", " ").replace('"', " ")
    return {"operation": "jira.search_issues",
            "payload": {"cloudId": defaults.get("cloud_id", "<cloud_id>"),
                        "jql": 'project = %s AND issuetype = Epic AND statusCategory != Done AND text ~ "%s" ORDER BY updated DESC' % (project, safe),
                        "maxResults": 10, "fields": ["summary", "status"]}}


def _names(items):
    return sorted(i.get("name") if isinstance(i, dict) else str(i) for i in items or [])


def diff(draft, result):
    fields = result.get("fields", result) if isinstance(result, dict) else {}
    key = result.get("key") if isinstance(result, dict) else None
    mismatches, unverifiable = [], []

    def check(name, expected, got):
        if expected != got:
            mismatches.append({"field": name, "expected": expected, "actual": got})

    if "summary" in draft:
        check("summary", draft["summary"], (fields.get("summary") or "").strip())
    if "issue_type" in draft and draft["operation"] == "create":
        issuetype = fields.get("issuetype") or {}
        check("issue_type", draft["issue_type"], issuetype.get("name") if isinstance(issuetype, dict) else issuetype)
    if "labels" in draft:
        check("labels", sorted(draft["labels"]), sorted(fields.get("labels") or []))
    if "components" in draft:
        check("components", sorted(draft["components"]), _names(fields.get("components")))
    if "priority" in draft:
        priority = fields.get("priority") or {}
        check("priority", draft["priority"], priority.get("name") if isinstance(priority, dict) else priority)
    if "parent" in draft:
        parent = fields.get("parent") or {}
        check("parent", draft["parent"], parent.get("key") if isinstance(parent, dict) else parent)
    if "assignee" in draft:
        assignee = fields.get("assignee") or {}
        check("assignee", draft["assignee"], assignee.get("accountId") if isinstance(assignee, dict) else assignee)
    if draft.get("description"):
        if not fields.get("description"):
            mismatches.append({"field": "description", "expected": "non-empty", "actual": fields.get("description")})
        else:
            unverifiable.append("description content (Jira re-renders markdown; only non-empty was checked)")
    for fid in draft.get("fields", {}):
        unverifiable.append("%s (custom field shapes vary; compare by eye)" % fid)
    if key and draft["operation"] == "update" and draft.get("key") and key != draft["key"]:
        mismatches.append({"field": "key", "expected": draft["key"], "actual": key})
    return mismatches, unverifiable, key or draft.get("key")
