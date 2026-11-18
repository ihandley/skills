#!/usr/bin/env python3
"""forecaster: seeded Monte Carlo forecast for one epic from saved weekly Pace.

Stdlib only. Never touches the network or a credential.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from datetime import date, timedelta
from pathlib import Path

MIN_PYTHON = (3, 11)
LIKELY_PERCENTILE = 50
DUE_PERCENTILE = 85
DEFAULT_TRIALS = 10000
DEFAULT_EXPIRY_DAYS = 28
MAX_WEEKS = 520
REFRESH_TRIGGER = (
    "Rerun when the expiry date passes, when remaining points change by more than 10 percent, "
    "or when a new week of Pace is saved."
)


POINTS_FIELD = "customfield_10016"
WINDOW_WEEKS = 12
COUNT_STATUSES = ("Testing", "Done")
CANCELED = "Canceled"
MIN_ACTIVE_WEEKS = 6
VOLATILE_CV = 1.0
SEARCH_FIELDS = ["summary", "status", "parent", "subtasks", "assignee"]


class Refusal(Exception):
    pass


def load_json(path: Path, what: str):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise Refusal(f"{what} not found: {path}")
    except json.JSONDecodeError as exc:
        raise Refusal(f"{what} is not valid JSON ({path}): {exc}")


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def as_of_date(data: dict) -> date:
    return date.fromisoformat(data["as_of"]) if data.get("as_of") else date.today()


def window_start(data: dict) -> date:
    return monday(as_of_date(data)) - timedelta(weeks=WINDOW_WEEKS)


def queries(inputs_path: Path) -> dict:
    data = load_json(inputs_path, "inputs file")
    if not data.get("assignee"):
        raise Refusal("inputs file is missing required field: assignee")
    field = data.get("points_field", POINTS_FIELD)
    start = window_start(data).isoformat()
    jql = (
        f'assignee = "{data["assignee"]}" AND status changed TO ("Testing", "Done") '
        f'AFTER "{start}" ORDER BY updated ASC'
    )
    return {
        "operations": [{
            "purpose": "pace",
            "tool": "searchJiraIssuesUsingJql",
            "jql": jql,
            "fields": SEARCH_FIELDS + [field],
            "expand": "changelog",
            "note": "Page through every result; keep each page.",
        }],
        "save_results_note": (
            "Save the raw results (one object, or a list of pages, each with an issues list) to a file "
            "and set jira_results_file in the inputs file to its path, relative to the inputs file."
        ),
        "points_field": field,
    }


def first_count_date(issue: dict) -> date | None:
    days = []
    for h in issue.get("changelog", {}).get("histories", []):
        if any(i.get("field") == "status" and i.get("toString") in COUNT_STATUSES for i in h.get("items", [])):
            days.append(date.fromisoformat(h["created"][:10]))
    return min(days) if days else None


def ended_canceled(issue: dict) -> bool:
    if (issue.get("fields", {}).get("status") or {}).get("name") == CANCELED:
        return True
    moves = sorted(
        (h["created"], i["toString"])
        for h in issue.get("changelog", {}).get("histories", [])
        for i in h.get("items", []) if i.get("field") == "status"
    )
    return bool(moves) and moves[-1][1] == CANCELED


def pace_from_results(data: dict, base: Path) -> tuple[list[dict], list[str], list[str]]:
    raw = load_json(base / data["jira_results_file"], "Jira results file")
    pages = raw if isinstance(raw, list) else [raw]
    issues = [i for page in pages for i in page.get("issues", [])]
    field = data.get("points_field", POINTS_FIELD)
    parents = {(i.get("fields", {}).get("parent") or {}).get("key") for i in issues}
    start = window_start(data)
    end = start + timedelta(weeks=WINDOW_WEEKS)
    totals = {start + timedelta(weeks=n): 0.0 for n in range(WINDOW_WEEKS)}
    unpointed, pointed_seen = [], 0
    for issue in issues:
        f = issue.get("fields", {})
        if ended_canceled(issue) or f.get("subtasks") or issue.get("key") in parents:
            continue
        counted = first_count_date(issue)
        if counted is None or not (start <= counted < end):
            continue
        pts = f.get(field)
        if not pts:
            unpointed.append(issue["key"])
            continue
        pointed_seen += 1
        totals[monday(counted)] += float(pts)
    warnings = []
    if unpointed:
        warnings.append(
            f"Unpointed tickets left out of Pace ({len(unpointed)}): {', '.join(unpointed)}. Fix the points before trusting the dates."
        )
    if unpointed and not pointed_seen:
        raise Refusal(
            f"no history: the points field {field} is empty on every counted ticket ({', '.join(unpointed)}). "
            "Check the points_field input names the field this tenant populates."
        )
    history = [{"week": w.isoformat(), "points": int(p) if p == int(p) else p} for w, p in sorted(totals.items())]
    return history, warnings, unpointed


def history_warnings(history: list[dict]) -> list[str]:
    pts = [float(w.get("points", 0)) for w in history]
    warnings = []
    active = sum(1 for p in pts if p > 0)
    if len(pts) < WINDOW_WEEKS or active < MIN_ACTIVE_WEEKS:
        warnings.append(
            f"Short history: {active} of {len(pts)} weeks have points (want {WINDOW_WEEKS} weeks, at least {MIN_ACTIVE_WEEKS} active). Percentiles are weak."
        )
    mean = sum(pts) / len(pts) if pts else 0
    if mean > 0:
        sd = (sum((p - mean) ** 2 for p in pts) / len(pts)) ** 0.5
        if sd / mean > VOLATILE_CV:
            warnings.append(f"Volatile history: weekly Pace varies widely (stdev {sd:.1f} on mean {mean:.1f}). Percentiles are weak.")
    return warnings


def load_history(data: dict, base: Path) -> tuple[list[dict], list[str], list[str]]:
    warnings, unpointed = [], []
    history = data.get("history")
    if history is None and data.get("history_file"):
        history = load_json(base / data["history_file"], "history file")
    if history is None and data.get("jira_results_file"):
        history, warnings, unpointed = pace_from_results(data, base)
    history = history or []
    if not any(float(w.get("points", 0)) > 0 for w in history):
        raise Refusal("no history: saved weekly Pace is empty or has no points, so no date can be forecast.")
    return history, warnings + history_warnings(history), unpointed


POINTS_FIELD = "customfield_10016"
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]*-\d+$")
NOT_IN_DATES_STATUS = "testing"


def scope_queries(key: str) -> dict:
    if not KEY_RE.match(key):
        raise Refusal(f"not a Jira key: {key!r}")
    fields = ["summary", "issuetype", "status", "parent", "subtasks", "issuelinks", POINTS_FIELD]
    epics = _epic_subquery(key)
    return {
        "points_field": POINTS_FIELD,
        "note": (
            "Run the operations in order with the Atlassian tool, paging through every result. Fill {epic_keys} and "
            "{ticket_keys} (comma-separated) from the earlier results. Save all issues merged as "
            f'{{"issues": [...]}} JSON and point scope_file at it. Points are read from {POINTS_FIELD}.'
        ),
        "operations": [
            {"operation": "jira.search", "purpose": "epics with Blocks links",
             "payload": {"jql": epics, "fields": fields}},
            {"operation": "jira.search", "purpose": "tickets under those epics", "needs": ["epic_keys"],
             "payload": {"jql": "issuetype != Epic AND parent in ({epic_keys})", "fields": fields}},
            {"operation": "jira.search", "purpose": "sub-tasks of those tickets", "needs": ["ticket_keys"],
             "payload": {"jql": "parent in ({ticket_keys})", "fields": fields}},
        ],
    }


def _epic_subquery(key: str) -> str:
    return f"issuetype = Epic AND (parent = {key} OR key = {key})"


def _blocks(issue: dict) -> list[tuple[str, str]]:
    """(blocker, blocked) pairs this issue's Blocks links state."""
    me = issue["key"]
    pairs = []
    for link in issue["fields"].get("issuelinks") or []:
        if (link.get("type") or {}).get("name") != "Blocks":
            continue
        if "outwardIssue" in link:
            pairs.append((me, link["outwardIssue"]["key"]))
        if "inwardIssue" in link:
            pairs.append((link["inwardIssue"]["key"], me))
    return pairs


def propose_order(epic_keys: list[str], pairs: list[tuple[str, str]], warnings: list[str]) -> list[str]:
    keys = sorted(epic_keys)
    edges = {(a, b) for a, b in pairs if a in keys and b in keys and a != b}
    order: list[str] = []
    left = list(keys)
    while left:
        ready = [k for k in left if not any(b == k and a in left for a, b in edges)]
        if not ready:
            warnings.append("Blocks links form a cycle among " + ", ".join(left) + "; order for these falls back to key order. Confirm the order.")
            ready = [left[0]]
        order.append(ready[0])
        left.remove(ready[0])
    return order


def scope(data: dict, base: Path) -> dict:
    saved = load_json(base / data["scope_file"], "scope file")
    issues = {i["key"]: i for i in saved.get("issues", [])}
    epics = [k for k, i in issues.items() if i["fields"]["issuetype"]["name"] == "Epic"]
    warnings: list[str] = []

    def epic_of(issue: dict):
        seen = set()
        while issue and issue["key"] not in seen:
            seen.add(issue["key"])
            parent = (issue["fields"].get("parent") or {}).get("key")
            if parent in epics:
                return parent
            issue = issues.get(parent)
        return None

    pairs = [p for k in epics for p in _blocks(issues[k])]
    override = data.get("epic_order")
    if override:
        unknown = [k for k in override if k not in epics]
        if unknown:
            raise Refusal("epic_order names epics not in the saved scope: " + ", ".join(unknown))
        order = list(override) + [k for k in propose_order(epics, pairs, warnings) if k not in override]
        source = "inputs"
    else:
        order = propose_order(epics, pairs, warnings)
        source = "blocks"
    rows = {k: {"epic": k, "remaining_points": 0, "not_in_the_dates": 0} for k in order}
    for issue in issues.values():
        f = issue["fields"]
        if f["issuetype"]["name"] == "Epic" or f.get("subtasks"):
            continue
        epic = epic_of(issue)
        status = f["status"]
        if epic is None or status["statusCategory"]["key"] == "done" or status["name"].lower() == "canceled":
            continue
        pts = f.get(POINTS_FIELD)
        if pts is None:
            warnings.append(f"{issue['key']} is open and has no points; left out of the sums.")
        elif status["name"].lower() == NOT_IN_DATES_STATUS:
            rows[epic]["not_in_the_dates"] += pts
        else:
            rows[epic]["remaining_points"] += pts
    return {
        "initiative": data.get("initiative"),
        "order_source": source,
        "epics": [rows[k] for k in order],
        "not_in_the_dates": sum(r["not_in_the_dates"] for r in rows.values()),
        "warnings": warnings,
    }


def percentile(sorted_values: list[int], pct: int) -> int:
    rank = max(1, math.ceil(pct / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def simulate(remaining: float, paces: list[float], share: tuple[float, float], trials: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    weeks_needed = []
    for _ in range(trials):
        s = rng.uniform(*share)
        done, weeks = 0.0, 0
        while done < remaining and weeks < MAX_WEEKS:
            done += rng.choice(paces) * s
            weeks += 1
        weeks_needed.append(weeks)
    return sorted(weeks_needed)


def forecast(inputs_path: Path) -> dict:
    data = load_json(inputs_path, "inputs file")
    scoped = scope(data, inputs_path.parent) if data.get("scope_file") else None
    if scoped and "remaining_points" not in data:
        rows = {r["epic"]: r for r in scoped["epics"]}
        if data.get("epic") in rows:
            data["remaining_points"] = rows[data["epic"]]["remaining_points"]
        else:
            data["remaining_points"] = sum(r["remaining_points"] for r in scoped["epics"])
    for key in ("remaining_points", "start_date"):
        if key not in data:
            raise Refusal(f"inputs file is missing required field: {key}")
    history, warnings, unpointed = load_history(data, inputs_path.parent)
    start = date.fromisoformat(data["start_date"])
    share = data.get("capacity_share", [1, 1])
    share = (float(share[0]), float(share[-1]))
    seed = int(data.get("seed", 0))
    trials = int(data.get("trials", DEFAULT_TRIALS))
    expiry_days = int(data.get("expiry_days", DEFAULT_EXPIRY_DAYS))
    weeks = simulate(float(data["remaining_points"]), [float(w["points"]) for w in history], share, trials, seed)

    def at(pct: int) -> str:
        return (start + timedelta(weeks=percentile(weeks, pct))).isoformat()

    result = {
        "epic": data.get("epic"),
        "likely_date": at(LIKELY_PERCENTILE),
        "likely_percentile": LIKELY_PERCENTILE,
        "due_date": at(DUE_PERCENTILE),
        "due_percentile": DUE_PERCENTILE,
        "expiry": (start + timedelta(days=expiry_days)).isoformat(),
        "refresh_trigger": REFRESH_TRIGGER,
        "history": history,
        "warnings": warnings,
        "unpointed": unpointed,
        "inputs": {
            "remaining_points": data["remaining_points"],
            "start_date": data["start_date"],
            "capacity_share": list(share),
            "seed": seed,
            "trials": trials,
            "points_field": data.get("points_field", POINTS_FIELD),
        },
    }
    if scoped:
        result["scope"] = scoped
    return result


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print("forecaster needs Python 3.11 or newer.", file=sys.stderr)
        return 3
    parser = argparse.ArgumentParser(prog="forecaster")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("forecast", help="forecast one epic from an inputs file and saved Pace")
    p.add_argument("--inputs", required=True, type=Path)
    q = sub.add_parser("queries", help="emit the Jira operations to run; never calls Jira")
    qsub = q.add_subparsers(dest="mode", required=True)
    qp = qsub.add_parser("pace", help="resolved-ticket search with changelog for Pace")
    qp.add_argument("--inputs", required=True, type=Path)
    qs = qsub.add_parser("scope", help="initiative and epic search with Blocks links")
    qs.add_argument("--key", required=True, help="initiative or epic key")
    args = parser.parse_args(argv)
    try:
        if args.command == "queries":
            result = queries(args.inputs) if args.mode == "pace" else scope_queries(args.key)
        else:
            result = forecast(args.inputs)
    except Refusal as exc:
        print(f"forecaster: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
