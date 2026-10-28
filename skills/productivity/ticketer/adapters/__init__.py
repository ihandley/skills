"""Tracker adapters. Each adapter is a module exposing the same interface.

NAME, FIELDS ({draft key: "str" | "list" | "object"}), DRAFT_KEYS, MERGE_LIST_KEYS,
DISPLAY_ORDER, METADATA_KINDS, IDENT_KEYS, SUPPORTS_EXTRA, NORMALIZE_LABELS, CONFIG_TEMPLATE
find_parent(query, config) -> descriptor, or None when the tracker has no parent search
scope(draft), metadata_needs(draft, scope), store_metadata(data, kind, raw, issue_type),
validate(draft, config, metadata), build(draft, body_path), readback(draft),
diff(draft, result) -> (mismatches, unverifiable, ref)

Adapters are pure: no network, no credentials. Add a tracker by adding a module
here and registering it below.
"""

from __future__ import annotations

from . import github, jira

ADAPTERS = {jira.NAME: jira, github.NAME: github}


def get_adapter(name):
    try:
        return ADAPTERS[name]
    except KeyError:
        raise KeyError("unknown tracker %r; known: %s" % (name, ", ".join(sorted(ADAPTERS))))
