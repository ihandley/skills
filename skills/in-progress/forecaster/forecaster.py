#!/usr/bin/env python3
"""forecaster: seeded Monte Carlo forecast for one epic from saved weekly Pace.

Stdlib only. Never touches the network or a credential.
"""

from __future__ import annotations

import argparse
import json
import math
import random
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

    return {
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


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print("forecaster needs Python 3.11 or newer.", file=sys.stderr)
        return 3
    parser = argparse.ArgumentParser(prog="forecaster")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("forecast", help="forecast one epic from an inputs file and saved Pace")
    p.add_argument("--inputs", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = forecast(args.inputs)
    except Refusal as exc:
        print(f"forecaster: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
