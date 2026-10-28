"""Which Stepper item becomes active next.

Pure functions over a context dict (``{"items": [...]}``). Nothing here reads or
writes a file, and nothing raises: a caller turns a refusal into its own error.

A flat list is a tree with no parents, so one walk serves both shapes.
"""

from __future__ import annotations

DONE = ("verified", "cancelled")


def find(ctx: dict, item_id: str) -> dict | None:
    return next((item for item in ctx["items"] if item["id"] == item_id), None)


def children(ctx: dict, parent_id: str | None) -> list[dict]:
    return sorted(
        (item for item in ctx["items"] if item.get("parent_id") == parent_id),
        key=lambda item: item["order"],
    )


def descendants(ctx: dict, item: dict) -> list[dict]:
    found = []
    for child in children(ctx, item["id"]):
        found.append(child)
        found.extend(descendants(ctx, child))
    return found


def parent_of(ctx: dict, item: dict) -> dict | None:
    parent_id = item.get("parent_id")
    return None if parent_id is None else find(ctx, parent_id)


def eligible(ctx: dict, item: dict) -> bool:
    """True when every descendant is resolved, so the item itself may start."""
    return all(child["status"] in DONE for child in descendants(ctx, item))


def unmet(ctx: dict, item: dict) -> list[str]:
    """Ids this item depends on that are not yet resolved."""
    out = []
    for dep_id in item.get("depends_on") or []:
        dep = find(ctx, dep_id)
        if dep is None or dep["status"] not in DONE:
            out.append(dep_id)
    return out


def _branch(ctx: dict, node: dict) -> dict | None:
    if node["status"] != "pending":
        return None
    for child in children(ctx, node["id"]):
        chosen = _branch(ctx, child)
        if chosen is not None:
            return chosen
    if not children(ctx, node["id"]) or eligible(ctx, node):
        return node
    return None


def _after(ctx: dict, finished: dict) -> dict | None:
    for sibling in children(ctx, finished.get("parent_id")):
        if sibling["id"] == finished["id"]:
            continue
        chosen = _branch(ctx, sibling)
        if chosen is not None:
            return chosen
    parent = parent_of(ctx, finished)
    if parent is not None and parent["status"] == "pending" and eligible(ctx, parent):
        return parent
    if parent is not None:
        return _after(ctx, parent)
    return None


def choose_next(ctx: dict, finished: dict | None = None) -> dict | None:
    """The item that should become active, or None. ``finished`` is the item that just ended."""
    if finished is not None:
        return _after(ctx, finished)
    for top in children(ctx, None):
        chosen = _branch(ctx, top)
        if chosen is not None:
            return chosen
    return None


def demote_active(ctx: dict) -> None:
    for item in ctx["items"]:
        if item["status"] == "active":
            item["status"] = "pending"


def activate_next(ctx: dict, finished: dict | None = None) -> dict | None:
    chosen = choose_next(ctx, finished)
    if chosen is not None:
        chosen["status"] = "active"
    return chosen


def skip_target(ctx: dict, held: dict) -> tuple[dict | None, str | None]:
    """The next top-level item after ``held``, or None with the reason it cannot be."""
    later = [
        item for item in children(ctx, None)
        if item["order"] > held["order"] and item["status"] not in DONE
    ]
    if not later:
        return None, "no later item"
    target = later[0]
    if held["id"] in (target.get("depends_on") or []):
        return None, f"{target['id']} depends on {held['id']}; hold"
    blocked_by = unmet(ctx, target)
    if blocked_by:
        return None, f"{target['id']} depends on {', '.join(blocked_by)}"
    return target, None
