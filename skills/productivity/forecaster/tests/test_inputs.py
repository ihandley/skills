#!/usr/bin/env python3
"""CLI tests for `forecaster.py inputs check|set`. No Jira, agent, or network is involved."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

FORECASTER = Path(__file__).resolve().parents[1] / "forecaster.py"

COMPLETE = {
    "epic": "LV-1",
    "remaining_points": 40,
    "start_date": "2026-11-23",
    "history": [{"week": "2026-09-07", "points": 5}],
    "saved_on": "2026-11-18",
}


class InputsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "inputs.json"

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(FORECASTER), "inputs", *args, "--inputs", str(self.path)],
            capture_output=True, text=True,
        )

    def check(self):
        proc = self.run_cli("check")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def keys(self, report):
        return [m["key"] for m in report["missing"]]

    def write(self, data):
        self.path.write_text(json.dumps(data))

    def read(self):
        return json.loads(self.path.read_text())


class TestCheck(InputsCase):
    def test_absent_file_reports_every_required_input_with_a_question(self):
        report = self.check()
        self.assertFalse(report["complete"])
        self.assertEqual(self.keys(report), ["scope", "remaining", "start_date", "assignee", "pace"])
        for item in report["missing"]:
            self.assertTrue(item["question"].endswith("?"))

    def test_complete_file_reports_nothing_missing(self):
        self.write(COMPLETE)
        self.assertEqual(self.check(), {"complete": True, "missing": []})

    def test_only_the_gaps_are_reported(self):
        self.write({"epic": "LV-1", "start_date": "2026-11-23"})
        self.assertEqual(self.keys(self.check()), ["remaining", "assignee", "pace"])

    def test_initiative_counts_as_scope(self):
        self.write({**COMPLETE, "initiative": "LV-100", "epic": None})
        self.assertNotIn("scope", self.keys(self.check()))

    def test_scope_file_satisfies_remaining(self):
        data = {k: v for k, v in COMPLETE.items() if k != "remaining_points"}
        self.write({**data, "scope_file": "scope.json"})
        self.assertEqual(self.check()["missing"], [])

    def test_items_unit_needs_remaining_items(self):
        self.write({**COMPLETE, "unit": "items"})
        item = [m for m in self.check()["missing"] if m["key"] == "remaining"]
        self.assertEqual(len(item), 1)
        self.assertIn("tickets", item[0]["question"])

    def test_assignee_not_asked_when_pace_is_saved(self):
        self.write(COMPLETE)
        self.assertNotIn("assignee", self.keys(self.check()))

    def test_assignee_given_but_pace_unsaved_asks_for_the_jira_run(self):
        data = {k: v for k, v in COMPLETE.items() if k != "history"}
        self.write({**data, "assignee": "ian"})
        report = self.check()
        self.assertEqual(self.keys(report), ["pace"])
        self.assertIn("queries pace", report["missing"][0]["question"])

    def test_jira_results_file_and_history_file_satisfy_pace(self):
        data = {k: v for k, v in COMPLETE.items() if k != "history"}
        self.write({**data, "history_file": "x.json"})
        self.assertEqual(self.check()["missing"], [])
        self.write({**data, "jira_results_file": "x.json", "as_of": "2026-11-23"})
        self.assertEqual(self.check()["missing"], [])

    def test_results_file_without_as_of_reports_as_of_missing(self):
        data = {k: v for k, v in COMPLETE.items() if k != "history"}
        self.write({**data, "jira_results_file": "x.json"})
        report = self.check()
        self.assertEqual(self.keys(report), ["as_of"])
        self.assertIn("12 week window end", report["missing"][0]["question"])

    def test_blank_values_count_as_missing(self):
        self.write({**COMPLETE, "start_date": ""})
        self.assertEqual(self.keys(self.check()), ["start_date"])

    def test_bad_start_date_is_reported_not_accepted(self):
        self.write({**COMPLETE, "start_date": "next week"})
        self.assertEqual(self.keys(self.check()), ["start_date"])

    def test_invalid_json_refused(self):
        self.path.write_text("{nope")
        self.assertEqual(self.run_cli("check").returncode, 2)

    def test_check_never_writes(self):
        self.check()
        self.assertFalse(self.path.exists())


class TestSet(InputsCase):
    def set(self, *pairs):
        proc = self.run_cli("set", *pairs)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def test_creates_the_file_and_stamps_saved_on(self):
        self.set("epic=LV-1")
        data = self.read()
        self.assertEqual(data["epic"], "LV-1")
        self.assertEqual(data["saved_on"], date.today().isoformat())

    def test_values_parse_as_json_else_string(self):
        self.set("remaining_points=40", "capacity_share=[0.5, 0.7]", "assignee=ian.handley", "seed=7")
        data = self.read()
        self.assertEqual(data["remaining_points"], 40)
        self.assertEqual(data["capacity_share"], [0.5, 0.7])
        self.assertEqual(data["assignee"], "ian.handley")
        self.assertEqual(data["seed"], 7)

    def test_existing_keys_are_preserved_including_hand_edits(self):
        self.write({"epic": "LV-1", "december_factor": 0.6, "note": "hand written"})
        self.set("start_date=2026-11-23")
        data = self.read()
        self.assertEqual(data["december_factor"], 0.6)
        self.assertEqual(data["note"], "hand written")
        self.assertEqual(data["epic"], "LV-1")

    def test_set_overwrites_the_named_key_only(self):
        self.write({"epic": "LV-1", "start_date": "2026-11-23"})
        self.set("epic=LV-2")
        self.assertEqual(self.read()["start_date"], "2026-11-23")
        self.assertEqual(self.read()["epic"], "LV-2")

    def test_output_reports_what_is_still_missing(self):
        out = self.set("epic=LV-1")
        self.assertIn("start_date", [m["key"] for m in out["missing"]])
        self.assertFalse(out["complete"])

    def test_set_until_complete_then_check_asks_nothing(self):
        self.set("epic=LV-1", "remaining_points=40", "start_date=2026-11-23", "assignee=ian")
        self.set('history=[{"week": "2026-09-07", "points": 5}]')
        self.assertEqual(self.check(), {"complete": True, "missing": []})

    def test_dates_are_validated(self):
        for pair in ("start_date=soon", "as_of=2026-13-01", 'history=[{"week": "Mon", "points": 1}]'):
            proc = self.run_cli("set", pair)
            self.assertEqual(proc.returncode, 2, pair)
        self.assertFalse(self.path.exists())

    def test_history_must_be_a_list_of_week_points(self):
        self.assertEqual(self.run_cli("set", "history=5").returncode, 2)
        self.assertEqual(self.run_cli("set", 'history=[{"week": "2026-09-07"}]').returncode, 2)

    def test_unknown_key_refused(self):
        proc = self.run_cli("set", "epik=LV-1")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("epik", proc.stderr)

    def test_malformed_pair_refused(self):
        self.assertEqual(self.run_cli("set", "epic").returncode, 2)

    def test_saved_on_is_stamped_by_set_and_refused_as_an_answer(self):
        self.assertEqual(self.run_cli("set", "saved_on=2020-01-01").returncode, 2)
        self.set("epic=LV-1")
        self.assertEqual(self.read()["saved_on"], date.today().isoformat())

    def test_set_does_not_default_as_of(self):
        self.set("epic=LV-1", "jira_results_file=x.json")
        self.assertNotIn("as_of", self.read())

    def test_saved_file_feeds_forecast(self):
        self.set("epic=LV-1", "remaining_points=20", "start_date=2026-11-23", "seed=1", "trials=500",
                 'history=[{"week": "2026-09-07", "points": 5}, {"week": "2026-09-14", "points": 7}]')
        proc = subprocess.run([sys.executable, str(FORECASTER), "forecast", "--inputs", str(self.path)],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("2026-09-07", json.dumps(json.loads(proc.stdout)["history"]))


if __name__ == "__main__":
    unittest.main()
