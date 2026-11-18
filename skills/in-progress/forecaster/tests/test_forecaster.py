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


PTS = "customfield_10016"


def issue(key, points, history, status="Done", parent=None, subtasks=None, pts_field=PTS):
    fields = {"status": {"name": status}, "subtasks": [{"key": k} for k in (subtasks or [])]}
    if points is not None:
        fields[pts_field] = points
    if parent:
        fields["parent"] = {"key": parent}
    histories = [
        {"created": f"{day}T10:00:00.000-0600", "items": [{"field": "status", "fromString": a, "toString": b}]}
        for day, a, b in history
    ]
    return {"key": key, "fields": fields, "changelog": {"histories": histories}}


# as_of 2026-11-23 (Monday): window is the 12 whole weeks 2026-08-31 .. 2026-11-16.
PACE_AS_OF = "2026-11-23"


class PaceCase(ForecastCase):
    def pace_inputs(self, issues, **over):
        (self.dir / "raw.json").write_text(json.dumps({"issues": issues}))
        data = inputs(as_of=PACE_AS_OF, assignee="ian", points_field=PTS, jira_results_file="raw.json")
        del data["history"]
        data.update(over)
        return data

    def pace(self, issues, **over):
        out = self.ok(self.pace_inputs(issues, **over))
        return {w["week"]: w["points"] for w in out["history"]}, out


class TestPaceCounting(PaceCase):
    def test_window_is_twelve_mondays_holiday_weeks_zero(self):
        weeks, out = self.pace([issue("A-1", 5, [("2026-10-06", "In Progress", "Done")])])
        self.assertEqual(len(weeks), 12)
        self.assertEqual(min(weeks), "2026-08-31")
        self.assertEqual(max(weeks), "2026-11-16")
        self.assertEqual(weeks["2026-10-05"], 5)
        self.assertEqual(sum(weeks.values()), 5)

    def test_counts_in_week_first_entering_testing_not_done(self):
        t = issue("A-1", 3, [("2026-09-02", "In Progress", "Testing"), ("2026-10-14", "Testing", "Done")])
        weeks, _ = self.pace([t])
        self.assertEqual(weeks["2026-08-31"], 3)
        self.assertEqual(weeks["2026-10-12"], 0)

    def test_first_entry_wins_after_reopen(self):
        t = issue("A-1", 3, [
            ("2026-10-14", "Testing", "Done"), ("2026-09-02", "In Progress", "Testing"),
            ("2026-10-20", "Done", "In Progress"), ("2026-10-27", "In Progress", "Done"),
        ])
        weeks, _ = self.pace([t])
        self.assertEqual(sum(weeks.values()), 3)
        self.assertEqual(weeks["2026-08-31"], 3)

    def test_canceled_never_counts(self):
        t = issue("A-1", 8, [("2026-10-06", "In Progress", "Canceled")], status="Canceled")
        t2 = issue("A-2", 8, [("2026-10-06", "In Progress", "Testing"), ("2026-10-07", "Testing", "Canceled")], status="Canceled")
        weeks, _ = self.pace([t, t2, issue("A-3", 2, [("2026-10-06", "In Progress", "Done")])])
        self.assertEqual(sum(weeks.values()), 2)

    def test_outside_window_ignored(self):
        old = issue("A-1", 5, [("2026-08-25", "In Progress", "Done")])
        cur = issue("A-2", 5, [("2026-11-24", "In Progress", "Done")])  # current, partial week
        weeks, _ = self.pace([old, cur, issue("A-3", 1, [("2026-11-16", "In Progress", "Done")])])
        self.assertEqual(sum(weeks.values()), 1)

    def test_parent_of_subtasks_not_counted(self):
        parent = issue("A-1", 8, [("2026-10-06", "In Progress", "Done")], subtasks=["A-2"])
        child = issue("A-2", 3, [("2026-10-06", "In Progress", "Done")], parent="A-1")
        weeks, _ = self.pace([parent, child])
        self.assertEqual(sum(weeks.values()), 3)

    def test_parent_detected_from_child_link_alone(self):
        parent = issue("A-1", 8, [("2026-10-06", "In Progress", "Done")])
        child = issue("A-2", 3, [("2026-10-06", "In Progress", "Done")], parent="A-1")
        weeks, _ = self.pace([parent, child])
        self.assertEqual(sum(weeks.values()), 3)

    def test_epic_parent_key_outside_results_does_not_hide_leaf(self):
        child = issue("A-2", 3, [("2026-10-06", "In Progress", "Done")], parent="EPIC-9")
        weeks, _ = self.pace([child])
        self.assertEqual(sum(weeks.values()), 3)


class TestPaceWarnings(PaceCase):
    def test_unpointed_listed_and_excluded(self):
        a = issue("A-1", None, [("2026-10-06", "In Progress", "Done")])
        z = issue("A-2", 0, [("2026-10-06", "In Progress", "Done")])
        b = issue("A-3", 5, [("2026-10-06", "In Progress", "Done")])
        weeks, out = self.pace([a, z, b])
        self.assertEqual(sum(weeks.values()), 5)
        self.assertEqual(out["unpointed"], ["A-1", "A-2"])
        self.assertTrue(any("A-1" in w and "A-2" in w and "unpointed" in w.lower() for w in out["warnings"]))

    def test_points_field_is_the_configured_one(self):
        t = issue("A-1", 4, [("2026-10-06", "In Progress", "Done")], pts_field="customfield_10002")
        t["fields"]["customfield_10016"] = 99
        weeks, out = self.pace([t], points_field="customfield_10002")
        self.assertEqual(sum(weeks.values()), 4)
        self.assertEqual(out["inputs"]["points_field"], "customfield_10002")

    def test_empty_points_field_warns(self):
        t = issue("A-1", 4, [("2026-10-06", "In Progress", "Done")], pts_field="customfield_10002")
        r = self.run_cli(self.pace_inputs([t]))
        self.assertEqual(r.returncode, 2)  # no points anywhere: refused as empty history
        self.assertIn("customfield_10016", r.stderr)
        self.assertIn("empty", r.stderr.lower())

    def test_short_history_warns(self):
        _, out = self.pace([issue("A-1", 5, [("2026-10-06", "In Progress", "Done")])])
        self.assertTrue(any("short" in w.lower() for w in out["warnings"]))

    def test_volatile_history_warns(self):
        hist = [{"week": f"2026-09-{d:02d}", "points": p} for d, p in zip(range(1, 13), [0, 40, 0, 1, 0, 30, 0, 2, 0, 50, 0, 1])]
        out = self.ok(inputs(history=hist))
        self.assertTrue(any("volatile" in w.lower() for w in out["warnings"]))

    def test_steady_full_history_has_no_history_warnings(self):
        hist = [{"week": f"2026-09-{d:02d}", "points": 10 + d % 3} for d in range(1, 13)]
        out = self.ok(inputs(history=hist))
        self.assertEqual(out["warnings"], [])

    def test_missing_results_file_refused(self):
        data = self.pace_inputs([])
        data["jira_results_file"] = "nope.json"
        r = self.run_cli(data)
        self.assertEqual(r.returncode, 2)
        self.assertIn("nope.json", r.stderr)

    def test_results_file_may_be_list_of_pages(self):
        (self.dir / "raw.json").write_text(json.dumps([
            {"issues": [issue("A-1", 2, [("2026-10-06", "In Progress", "Done")])]},
            {"issues": [issue("A-2", 3, [("2026-10-13", "In Progress", "Done")])]},
        ]))
        data = self.pace_inputs([])
        (self.dir / "raw.json").write_text(json.dumps([
            {"issues": [issue("A-1", 2, [("2026-10-06", "In Progress", "Done")])]},
            {"issues": [issue("A-2", 3, [("2026-10-13", "In Progress", "Done")])]},
        ]))
        out = self.ok(data)
        self.assertEqual(sum(w["points"] for w in out["history"]), 5)


class TestQueries(ForecastCase):
    def queries(self, data):
        path = self.dir / "q.json"
        path.write_text(json.dumps(data))
        r = subprocess.run([sys.executable, str(FORECASTER), "queries", "--inputs", str(path)],
                           capture_output=True, text=True)
        return r

    def test_emits_resolved_search_with_changelog_for_assignee(self):
        r = self.queries({"assignee": "ian.handley", "as_of": PACE_AS_OF, "points_field": PTS})
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        op = out["operations"][0]
        self.assertEqual(op["tool"], "searchJiraIssuesUsingJql")
        self.assertIn('assignee = "ian.handley"', op["jql"])
        self.assertIn("2026-08-31", op["jql"])
        self.assertIn("Testing", op["jql"])
        self.assertIn("Done", op["jql"])
        self.assertIn(PTS, op["fields"])
        for f in ("status", "parent", "subtasks"):
            self.assertIn(f, op["fields"])
        self.assertEqual(op["expand"], "changelog")
        self.assertIn("jira_results_file", out["save_results_note"])

    def test_missing_assignee_refused(self):
        r = self.queries({"as_of": PACE_AS_OF})
        self.assertEqual(r.returncode, 2)
        self.assertIn("assignee", r.stderr)

    def test_script_holds_no_credential_and_no_network(self):
        src = FORECASTER.read_text()
        for word in ("urllib", "socket", "http.client", "requests", "subprocess", "token", "password", "os.environ", "getenv"):
            self.assertNotIn(word, src.lower().replace("jira_results_file", ""), word)


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
