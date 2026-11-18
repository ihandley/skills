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


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class TestQueriesScope(unittest.TestCase):
    def run_q(self, *args):
        return subprocess.run([sys.executable, str(FORECASTER), "queries", "scope", *args],
                              capture_output=True, text=True)

    def test_emits_initiative_epic_search_with_blocks_links(self):
        r = self.run_q("--key", "LV-1")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        op = out["operations"][0]
        self.assertEqual(op["operation"], "jira.search")
        jql = op["payload"]["jql"]
        self.assertIn("LV-1", jql)
        self.assertIn("issuetype = Epic", jql)
        self.assertIn("issuelinks", op["payload"]["fields"])
        self.assertIn("customfield_10016", op["payload"]["fields"])
        self.assertIn("issuelinks", " ".join(out["operations"][0]["payload"]["fields"]))

    def test_second_operation_searches_child_tickets(self):
        out = json.loads(self.run_q("--key", "LV-1").stdout)
        self.assertEqual(len(out["operations"]), 3)
        self.assertIn("parent in", out["operations"][1]["payload"]["jql"])

    def test_key_is_escaped(self):
        r = self.run_q("--key", 'LV-1" OR project = X')
        self.assertNotEqual(r.returncode, 0)

    def test_key_required(self):
        self.assertNotEqual(self.run_q().returncode, 0)


class TestScope(ForecastCase):
    def scoped(self, **over):
        data = inputs(scope_file=str(FIXTURES / "scope_search.json"), initiative="LV-1")
        del data["remaining_points"]
        data.update(over)
        return self.ok(data)["scope"]

    def test_order_proposed_from_blocks_links(self):
        # LV-12 blocks LV-10 blocks LV-11, so key order is wrong.
        s = self.scoped()
        self.assertEqual([e["epic"] for e in s["epics"]], ["LV-12", "LV-10", "LV-11"])
        self.assertEqual(s["order_source"], "blocks")

    def test_order_overridable_in_inputs(self):
        s = self.scoped(epic_order=["LV-11", "LV-10", "LV-12"])
        self.assertEqual([e["epic"] for e in s["epics"]], ["LV-11", "LV-10", "LV-12"])
        self.assertEqual(s["order_source"], "inputs")

    def test_override_with_unknown_epic_refused(self):
        data = inputs(scope_file=str(FIXTURES / "scope_search.json"), epic_order=["LV-99"])
        r = self.run_cli(data)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("LV-99", r.stderr)

    def test_remaining_is_sum_of_open_leaf_points(self):
        # LV-10: story 5 (open leaf); done, canceled, unpointed and testing excluded.
        # LV-11: parent 13 is not a leaf; its sub-task 2 + story 3.
        rem = {e["epic"]: e["remaining_points"] for e in self.scoped()["epics"]}
        self.assertEqual(rem, {"LV-12": 2, "LV-10": 5, "LV-11": 5})

    def test_testing_points_reported_not_in_the_dates(self):
        by = {e["epic"]: e for e in self.scoped()["epics"]}
        self.assertEqual(by["LV-10"]["not_in_the_dates"], 3)
        self.assertEqual(by["LV-11"]["not_in_the_dates"], 0)
        self.assertEqual(self.scoped()["not_in_the_dates"], 3)

    def test_unpointed_open_tickets_warned(self):
        s = self.scoped()
        self.assertTrue(any("LV-105" in w for w in s["warnings"]))
        self.assertFalse(any("LV-104" in w for w in s["warnings"]))

    def test_epic_forecast_uses_scope_remaining_when_not_given(self):
        data = inputs(scope_file=str(FIXTURES / "scope_search.json"), epic="LV-10", seed=3)
        del data["remaining_points"]
        out = self.ok(data)
        self.assertEqual(out["inputs"]["remaining_points"], 5)

    def test_missing_scope_file_refused(self):
        r = self.run_cli(inputs(scope_file="nope.json"))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("nope.json", r.stderr)

    def test_blocks_cycle_warns_and_keeps_all_epics(self):
        d = json.loads((FIXTURES / "scope_search.json").read_text())
        for i in d["issues"]:
            if i["key"] == "LV-11":
                i["fields"]["issuelinks"] = [{"type": {"name": "Blocks"}, "outwardIssue": {"key": "LV-12"}}]
        (self.dir / "cyc.json").write_text(json.dumps(d))
        s = self.scoped(scope_file=str(self.dir / "cyc.json"))
        self.assertEqual(sorted(e["epic"] for e in s["epics"]), ["LV-10", "LV-11", "LV-12"])
        self.assertTrue(any("cycle" in w.lower() for w in s["warnings"]))


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
