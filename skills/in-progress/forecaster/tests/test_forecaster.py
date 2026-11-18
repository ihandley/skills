#!/usr/bin/env python3
"""CLI tests for forecaster. No Jira, agent, or network is involved."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FORECASTER = Path(__file__).resolve().parents[1] / "forecaster.py"

HISTORY = [
    {"week": "2026-08-31", "points": 8},
    {"week": "2026-09-07", "points": 5},
    {"week": "2026-09-14", "points": 13},
    {"week": "2026-09-21", "points": 3},
    {"week": "2026-09-28", "points": 8},
    {"week": "2026-10-05", "points": 10},
]


def inputs(**over):
    base = {
        "epic": "LV-1",
        "remaining_points": 60,
        "start_date": "2026-11-23",
        "capacity_share": [0.5, 0.7],
        "seed": 7,
        "trials": 2000,
        "history": HISTORY,
    }
    base.update(over)
    return base


class ForecastCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_cli(self, data, *extra, name="inputs.json"):
        path = self.dir / name
        path.write_text(json.dumps(data))
        return subprocess.run(
            [sys.executable, str(FORECASTER), "forecast", "--inputs", str(path), *extra],
            capture_output=True, text=True,
        )

    def ok(self, data, *extra):
        r = self.run_cli(data, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class TestDeterminism(ForecastCase):
    def test_same_seed_same_output(self):
        a = self.run_cli(inputs())
        b = self.run_cli(inputs())
        self.assertEqual(a.stdout, b.stdout)
        out = json.loads(a.stdout)
        self.assertRegex(out["likely_date"], r"^\d{4}-\d\d-\d\d$")
        self.assertRegex(out["due_date"], r"^\d{4}-\d\d-\d\d$")

    def test_due_date_not_before_likely_date(self):
        out = self.ok(inputs())
        self.assertGreaterEqual(out["due_date"], out["likely_date"])
        self.assertGreater(out["likely_date"], "2026-11-23")

    def test_constant_pace_gives_exact_date(self):
        hist = [{"week": f"2026-09-{d:02d}", "points": 10} for d in (7, 14, 21)]
        out = self.ok(inputs(history=hist, capacity_share=[1, 1], remaining_points=30))
        # 3 full weeks of 10 points from 2026-11-23 finish on 2026-12-14.
        self.assertEqual(out["likely_date"], "2026-12-14")
        self.assertEqual(out["due_date"], "2026-12-14")

    def test_different_seed_may_differ_but_each_is_stable(self):
        a = self.ok(inputs(seed=1))
        b = self.ok(inputs(seed=1))
        self.assertEqual(a, b)

    def test_history_dates_are_kept_in_output(self):
        out = self.ok(inputs())
        self.assertEqual(out["history"], HISTORY)
        self.assertEqual(out["inputs"]["start_date"], "2026-11-23")
        self.assertEqual(out["inputs"]["seed"], 7)


class TestExpiry(ForecastCase):
    def test_forecast_carries_expiry_and_refresh_trigger(self):
        out = self.ok(inputs())
        self.assertEqual(out["expiry"], "2026-12-21")  # start_date + 28 days
        self.assertTrue(out["refresh_trigger"].strip())

    def test_expiry_days_is_an_input(self):
        out = self.ok(inputs(expiry_days=14))
        self.assertEqual(out["expiry"], "2026-12-07")

    def test_percentiles_are_labelled(self):
        out = self.ok(inputs())
        self.assertEqual(out["likely_percentile"], 50)
        self.assertEqual(out["due_percentile"], 85)


class TestEmptyHistory(ForecastCase):
    def test_empty_history_refused(self):
        r = self.run_cli(inputs(history=[]))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no history", r.stderr.lower())
        self.assertEqual(r.stdout.strip(), "")

    def test_missing_history_refused(self):
        data = inputs()
        del data["history"]
        r = self.run_cli(data)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no history", r.stderr.lower())

    def test_all_zero_history_refused(self):
        hist = [{"week": "2026-09-07", "points": 0}]
        r = self.run_cli(inputs(history=hist))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("no history", r.stderr.lower())


class TestHistoryFile(ForecastCase):
    def test_history_read_from_file_beside_inputs(self):
        (self.dir / "hist.json").write_text(json.dumps(HISTORY))
        data = inputs(history_file="hist.json")
        del data["history"]
        out = self.ok(data)
        self.assertEqual(out["history"], HISTORY)
        self.assertEqual(out, self.ok(inputs()) | {"inputs": out["inputs"]})


class TestBadInputs(ForecastCase):
    def test_missing_remaining_points_refused(self):
        data = inputs()
        del data["remaining_points"]
        r = self.run_cli(data)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("remaining_points", r.stderr)

    def test_missing_inputs_file_refused(self):
        r = subprocess.run(
            [sys.executable, str(FORECASTER), "forecast", "--inputs", str(self.dir / "nope.json")],
            capture_output=True, text=True,
        )
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nope.json", r.stderr)


class TestInvocation(unittest.TestCase):
    root = FORECASTER.parent

    def test_user_invoked_only(self):
        skill = (self.root / "SKILL.md").read_text()
        self.assertIn("disable-model-invocation: true", skill.split("---")[1])
        yaml = (self.root / "agents" / "openai.yaml").read_text()
        self.assertIn("allow_implicit_invocation: false", yaml)

    def test_listed_in_in_progress_readme(self):
        readme = (self.root.parent / "README.md").read_text()
        self.assertIn("[forecaster](forecaster/SKILL.md)", readme)


if __name__ == "__main__":
    unittest.main()
