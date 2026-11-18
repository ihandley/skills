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
UNITS = ("points", "items")
DEFAULT_UNIT = "points"


def refresh_trigger(unit: str) -> str:
    return (
        f"Rerun when the expiry date passes, when remaining {unit} change by more than 10 percent, "
        "or when a new week of Pace is saved."
    )


ASSUMED = "assumed, not measured"
NO_SOAK_NOTE = "No soak length is set, so production has no date. Set soak_weeks to get one."
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


def pace_from_results(data: dict, base: Path, unit: str = DEFAULT_UNIT) -> tuple[list[dict], list[str], list[str]]:
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
        if unit == "items":
            totals[monday(counted)] += 1
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


def load_history(data: dict, base: Path, unit: str = DEFAULT_UNIT) -> tuple[list[dict], list[str], list[str]]:
    warnings, unpointed = [], []
    history = data.get("history")
    if history is None and data.get("history_file"):
        history = load_json(base / data["history_file"], "history file")
    if history is None and data.get("jira_results_file"):
        history, warnings, unpointed = pace_from_results(data, base, unit)
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


def scope(data: dict, base: Path, unit: str = DEFAULT_UNIT) -> dict:
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
    remaining_key = f"remaining_{unit}"
    parked_key = "not_in_the_dates" if unit == "points" else f"not_in_the_dates_{unit}"
    rows = {k: {"epic": k, remaining_key: 0, parked_key: 0} for k in order}
    for issue in issues.values():
        f = issue["fields"]
        if f["issuetype"]["name"] == "Epic" or f.get("subtasks"):
            continue
        epic = epic_of(issue)
        status = f["status"]
        if epic is None or status["statusCategory"]["key"] == "done" or status["name"].lower() == "canceled":
            continue
        pts = 1 if unit == "items" else f.get(POINTS_FIELD)
        if pts is None:
            warnings.append(f"{issue['key']} is open and has no points; left out of the sums.")
        elif status["name"].lower() == NOT_IN_DATES_STATUS:
            rows[epic][parked_key] += pts
        else:
            rows[epic][remaining_key] += pts
    return {
        "initiative": data.get("initiative"),
        "order_source": source,
        "epics": [rows[k] for k in order],
        parked_key: sum(r[parked_key] for r in rows.values()),
        "warnings": warnings,
    }


def percentile(sorted_values: list[int], pct: int) -> int:
    rank = max(1, math.ceil(pct / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def parse_share(raw) -> tuple[float, float]:
    vals = [raw] if isinstance(raw, (int, float)) and not isinstance(raw, bool) else raw
    ok = (
        isinstance(vals, list) and len(vals) in (1, 2)
        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals)
    )
    if ok:
        low, high = float(vals[0]), float(vals[-1])
        ok = 0 < low <= high <= 1
    if not ok:
        raise Refusal(f"capacity_share must be a number or [low, high] with 0 < low <= high <= 1, got {raw!r}")
    return low, high


def parse_december_factor(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw <= 0:
        raise Refusal(f"december_factor must be a number above 0, got {raw!r}")
    return float(raw)


def parse_soak_weeks(raw) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise Refusal(f"soak_weeks must be a whole number of weeks, 0 or more, got {raw!r}")
    return raw


def parse_freezes(raw) -> list[tuple[date, date, str | None]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise Refusal(f"freezes must be a list of {{start, end}} dates, got {raw!r}")
    out = []
    for f in raw:
        try:
            start, end = date.fromisoformat(f["start"]), date.fromisoformat(f["end"])
        except (TypeError, KeyError, ValueError):
            raise Refusal(f"freezes entries need ISO start and end dates, got {f!r}")
        if end < start:
            raise Refusal(f"freezes entry ends before it starts: {f!r}")
        out.append((start, end, f.get("name")))
    return out


def clear_of_freezes(day: date, freezes: list[tuple[date, date, str | None]]) -> date:
    moved = True
    while moved:
        moved = False
        for start, end, _ in freezes:
            if start <= day <= end:
                day, moved = end + timedelta(days=1), True
    return day


def simulate_chain(cumulative: list[float], paces: list[float], share: tuple[float, float], trials: int, seed: int,
                   week_factor=lambda week: 1.0) -> list[list[int]]:
    """Run the epics in order in each trial. cumulative[i] is points needed through epic i.

    Returns, per epic, the sorted weeks at which each whole run finished that epic.
    """
    rng = random.Random(seed)
    per_epic: list[list[int]] = [[] for _ in cumulative]
    for _ in range(trials):
        s = rng.uniform(*share)
        done, weeks, i = 0.0, 0, 0
        while i < len(cumulative):
            while i < len(cumulative) and done >= cumulative[i]:
                per_epic[i].append(weeks)
                i += 1
            if i == len(cumulative):
                break
            if weeks >= MAX_WEEKS:
                for j in range(i, len(cumulative)):
                    per_epic[j].append(weeks)
                break
            done += rng.choice(paces) * s * week_factor(weeks)
            weeks += 1
    return [sorted(w) for w in per_epic]


def simulate(remaining: float, paces: list[float], share: tuple[float, float], trials: int, seed: int) -> list[int]:
    return simulate_chain([remaining], paces, share, trials, seed)[0]


def parse_percentiles(text: str | None) -> list[int]:
    if text is None:
        return [LIKELY_PERCENTILE, DUE_PERCENTILE]
    try:
        levels = [int(p) for p in text.split(",")]
    except ValueError:
        levels = []
    if not levels or any(not 1 <= p <= 100 for p in levels):
        raise Refusal(f"percentiles must be a comma-separated list of whole numbers from 1 to 100, got {text!r}")
    return sorted(set(levels))


def forecast(inputs_path: Path, percentiles: str | None = None, unit: str | None = None) -> dict:
    levels = parse_percentiles(percentiles)
    data = load_json(inputs_path, "inputs file")
    unit = unit or data.get("unit") or DEFAULT_UNIT
    if unit not in UNITS:
        raise Refusal(f"unit must be one of {', '.join(UNITS)}, got {unit!r}")
    remaining_key = f"remaining_{unit}"
    scoped = scope(data, inputs_path.parent, unit) if data.get("scope_file") else None
    rows = {r["epic"]: r for r in scoped["epics"]} if scoped else {}
    chain_epics = None
    if scoped and remaining_key not in data:
        if data.get("epic") in rows:
            data[remaining_key] = rows[data["epic"]][remaining_key]
        else:
            chain_epics = scoped["epics"]
            data[remaining_key] = sum(r[remaining_key] for r in chain_epics)
    for key in (remaining_key, "start_date"):
        if key not in data:
            raise Refusal(f"inputs file is missing required field: {key}")
    history, warnings, unpointed = load_history(data, inputs_path.parent, unit)
    start = date.fromisoformat(data["start_date"])
    share = parse_share(data.get("capacity_share", [1, 1]))
    december = parse_december_factor(data.get("december_factor"))
    soak = parse_soak_weeks(data.get("soak_weeks"))
    freezes = parse_freezes(data.get("freezes"))
    seed = int(data.get("seed", 0))
    trials = int(data.get("trials", DEFAULT_TRIALS))
    expiry_days = int(data.get("expiry_days", DEFAULT_EXPIRY_DAYS))
    paces = [float(w["points"]) for w in history]
    if chain_epics:
        cumulative, total = [], 0.0
        for r in chain_epics:
            total += r[remaining_key]
            cumulative.append(total)
    else:
        cumulative = [float(data[remaining_key])]
    def week_factor(week: int) -> float:
        return december if december and (start + timedelta(weeks=week)).month == 12 else 1.0

    all_weeks = simulate_chain(cumulative, paces, share, trials, seed, week_factor)

    def at(weeks: list[int], pct: int) -> str:
        return (start + timedelta(weeks=percentile(weeks, pct))).isoformat()

    def dates(weeks: list[int]) -> dict:
        return {str(p): at(weeks, p) for p in levels}

    def production(weeks: list[int]) -> dict:
        if soak is None:
            return {"likely_date": None, "due_date": None, "dates": {}, "note": NO_SOAK_NOTE}

        def cutover(pct: int) -> str:
            finish = start + timedelta(weeks=percentile(weeks, pct) + soak)
            return clear_of_freezes(finish, freezes).isoformat()

        return {
            "likely_date": cutover(LIKELY_PERCENTILE),
            "due_date": cutover(DUE_PERCENTILE),
            "dates": {str(p): cutover(p) for p in levels},
            "soak_weeks": soak,
            "note": None,
        }

    last = all_weeks[-1]
    assumptions = [{"factor": "capacity_share", "value": list(share), "label": ASSUMED}]
    if december is not None:
        assumptions.append({"factor": "december_factor", "value": december, "label": ASSUMED})
    if freezes:
        assumptions.append({
            "factor": "freezes",
            "value": [{"start": a.isoformat(), "end": b.isoformat(), "name": n} for a, b, n in freezes],
            "label": ASSUMED,
        })
    if soak is not None:
        assumptions.append({"factor": "soak_weeks", "value": soak, "label": ASSUMED})
    result = {
        "epic": data.get("epic"),
        "unit": unit,
        "likely_date": at(last, LIKELY_PERCENTILE),
        "likely_percentile": LIKELY_PERCENTILE,
        "due_date": at(last, DUE_PERCENTILE),
        "due_percentile": DUE_PERCENTILE,
        "percentiles": levels,
        "dates": dates(last),
        "production": production(last),
        "expiry": (start + timedelta(days=expiry_days)).isoformat(),
        "refresh_trigger": refresh_trigger(unit),
        "assumptions": assumptions,
        "history": history,
        "warnings": warnings,
        "unpointed": unpointed,
        "inputs": {
            remaining_key: data[remaining_key],
            "start_date": data["start_date"],
            "capacity_share": list(share),
            "seed": seed,
            "trials": trials,
            "points_field": data.get("points_field", POINTS_FIELD),
        },
    }
    if chain_epics:
        result["chain"] = [
            {
                "epic": r["epic"],
                remaining_key: r[remaining_key],
                "likely_date": at(w, LIKELY_PERCENTILE),
                "likely_percentile": LIKELY_PERCENTILE,
                "due_date": at(w, DUE_PERCENTILE),
                "due_percentile": DUE_PERCENTILE,
                "dates": dates(w),
                "production": production(w),
            }
            for r, w in zip(chain_epics, all_weeks)
        ]
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
    p.add_argument("--unit", choices=UNITS, help="count points (default) or tickets for Pace and remaining work")
    p.add_argument("--percentiles", help="comma-separated levels, default 50,85 (for example 50,70,95)")
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
            result = forecast(args.inputs, args.percentiles, args.unit)
    except Refusal as exc:
        print(f"forecaster: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
