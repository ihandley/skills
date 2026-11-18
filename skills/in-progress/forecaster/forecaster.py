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


class Refusal(Exception):
    pass


def load_json(path: Path, what: str):
    try:
        return json.loads(path.read_text())
    except FileNotFoundError:
        raise Refusal(f"{what} not found: {path}")
    except json.JSONDecodeError as exc:
        raise Refusal(f"{what} is not valid JSON ({path}): {exc}")


def load_history(data: dict, base: Path) -> list[dict]:
    history = data.get("history")
    if history is None and data.get("history_file"):
        history = load_json(base / data["history_file"], "history file")
    history = history or []
    if not any(float(w.get("points", 0)) > 0 for w in history):
        raise Refusal("no history: saved weekly Pace is empty or has no points, so no date can be forecast.")
    return history


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
    history = load_history(data, inputs_path.parent)
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
        "inputs": {
            "remaining_points": data["remaining_points"],
            "start_date": data["start_date"],
            "capacity_share": list(share),
            "seed": seed,
            "trials": trials,
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
    q = sub.add_parser("queries", help="emit the Jira operations to run")
    qsub = q.add_subparsers(dest="mode", required=True)
    qs = qsub.add_parser("scope", help="initiative and epic search with Blocks links")
    qs.add_argument("--key", required=True, help="initiative or epic key")
    args = parser.parse_args(argv)
    try:
        if args.command == "queries":
            print(json.dumps(scope_queries(args.key), indent=2))
            return 0
        result = forecast(args.inputs)
    except Refusal as exc:
        print(f"forecaster: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
