#!/usr/bin/env python3
"""CLI tests for forecaster. No Jira, agent, or network is involved."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
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
        r = subprocess.run([sys.executable, str(FORECASTER), "queries", "pace", "--inputs", str(path)],
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


def three_epics(a, b, c):
    out = two_epics(a, b)
    out["issues"] += [two_epics(0, 0)["issues"][0] | {"key": "LV-22"},
                      {"key": "LV-221", "fields": {"issuetype": {"name": "Story"}, "parent": {"key": "LV-22"}, "subtasks": [],
                       "customfield_10016": c, "status": {"name": "To Do", "statusCategory": {"key": "new"}}}}]
    return out


def two_epics(a, b):
    def epic(k):
        return {"key": k, "fields": {"issuetype": {"name": "Epic"}, "issuelinks": [], "parent": {"key": "LV-1"},
                "status": {"name": "To Do", "statusCategory": {"key": "new"}}}}
    def story(k, parent, pts):
        return {"key": k, "fields": {"issuetype": {"name": "Story"}, "parent": {"key": parent}, "subtasks": [],
                "customfield_10016": pts, "status": {"name": "To Do", "statusCategory": {"key": "new"}}}}
    issues = [epic("LV-20"), epic("LV-21"), story("LV-201", "LV-20", a)]
    if b:
        issues.append(story("LV-211", "LV-21", b))
    return {"issues": issues}


class TestChain(ForecastCase):
    def chain(self, *extra, **over):
        data = inputs(scope_file=str(FIXTURES / "scope_search.json"), initiative="LV-1")
        del data["remaining_points"]
        data.update(over)
        return self.ok(data, *extra)

    def test_each_epic_gets_likely_50_and_due_85_in_order(self):
        out = self.chain()
        rows = out["chain"]
        self.assertEqual([r["epic"] for r in rows], ["LV-12", "LV-10", "LV-11"])
        for r in rows:
            self.assertRegex(r["likely_date"], r"^\d{4}-\d\d-\d\d$")
            self.assertGreaterEqual(r["due_date"], r["likely_date"])
            self.assertEqual((r["likely_percentile"], r["due_percentile"]), (50, 85))
        self.assertEqual(out["likely_date"], rows[-1]["likely_date"])
        self.assertEqual(out["due_date"], rows[-1]["due_date"])

    def test_constant_pace_chain_dates_are_exact(self):
        # 10 points a week, share 1: LV-12 (2) done wk 1, LV-10 (5) cumulative 7 wk 1, LV-11 (5) cumulative 12 wk 2.
        hist = [{"week": f"2026-09-{d:02d}", "points": 10} for d in (7, 14, 21)]
        rows = self.chain(history=hist, capacity_share=[1, 1])["chain"]
        self.assertEqual([r["due_date"] for r in rows], ["2026-11-30", "2026-11-30", "2026-12-07"])

    def test_chain_percentile_is_from_whole_runs_not_summed(self):
        # Pace is 0 or 10 with equal odds; three epics of 10 points each need three good weeks.
        # Worked by hand: one epic's p85 is 3 weeks, the chain's p85 is 8 weeks, summed p85s would be 9.
        hist = [{"week": "2026-09-07", "points": 0}, {"week": "2026-09-14", "points": 10}]
        data = inputs(history=hist, capacity_share=[1, 1], trials=4000, seed=5,
                      scope_file=str(self.dir / "two.json"), initiative="LV-1")
        del data["remaining_points"]
        (self.dir / "two.json").write_text(json.dumps(three_epics(10, 10, 10)))
        rows = self.ok(data)["chain"]
        single = [self.ok(inputs(history=hist, capacity_share=[1, 1], trials=4000, seed=5,
                                 remaining_points=10))["due_date"]]
        weeks = lambda d: (date.fromisoformat(d) - date(2026, 11, 23)).days // 7
        self.assertEqual(weeks(single[0]), 3)
        self.assertEqual(weeks(rows[2]["due_date"]), 8)

    def test_later_epic_never_earlier(self):
        for seed in range(5):
            rows = self.chain(seed=seed)["chain"]
            for p in ("likely_date", "due_date"):
                dates = [r[p] for r in rows]
                self.assertEqual(dates, sorted(dates))

    def test_zero_remaining_epic_matches_epic_before(self):
        (self.dir / "z.json").write_text(json.dumps(two_epics(10, 0)))
        data = inputs(scope_file=str(self.dir / "z.json"), initiative="LV-1")
        del data["remaining_points"]
        rows = self.ok(data)["chain"]
        self.assertEqual(rows[0]["due_date"], rows[1]["due_date"])

    def test_percentiles_flag_selects_levels(self):
        out = self.chain("--percentiles", "50,70,95")
        for r in out["chain"]:
            self.assertEqual(list(r["dates"]), ["50", "70", "95"])
            self.assertLessEqual(r["dates"]["50"], r["dates"]["70"])
            self.assertLessEqual(r["dates"]["70"], r["dates"]["95"])
        self.assertEqual(out["percentiles"], [50, 70, 95])
        self.assertEqual(out["chain"][0]["dates"]["50"], out["chain"][0]["likely_date"])

    def test_default_percentiles_are_50_and_85(self):
        out = self.chain()
        self.assertEqual(out["percentiles"], [50, 85])
        self.assertEqual(out["chain"][0]["dates"]["85"], out["chain"][0]["due_date"])

    def test_bad_percentiles_refused(self):
        for bad in ("0", "101", "abc", "50,,70", ""):
            r = self.run_cli(inputs(), "--percentiles", bad)
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("percentiles", r.stderr)

    def test_single_epic_accepts_percentiles(self):
        out = self.ok(inputs(), "--percentiles", "50,95")
        self.assertEqual(out["percentiles"], [50, 95])
        self.assertEqual(out["dates"]["50"], out["likely_date"])
        self.assertNotIn("chain", out)

    def test_chain_is_deterministic(self):
        self.assertEqual(self.chain(seed=9), self.chain(seed=9))

    def test_named_epic_stays_a_single_epic_forecast(self):
        data = inputs(scope_file=str(FIXTURES / "scope_search.json"), epic="LV-10", seed=3)
        del data["remaining_points"]
        self.assertNotIn("chain", self.ok(data))


class TestCalendar(ForecastCase):
    FLAT = [{"week": f"2026-09-{d:02d}", "points": 10} for d in (7, 14, 21)]

    def flat(self, **over):
        return self.ok(inputs(history=self.FLAT, capacity_share=[1, 1], remaining_points=30, **over))

    # AC1
    def test_capacity_share_range_is_accepted_and_echoed(self):
        out = self.ok(inputs(capacity_share=[0.4, 0.6]))
        self.assertEqual(out["inputs"]["capacity_share"], [0.4, 0.6])

    def test_lower_share_finishes_later(self):
        hi = self.ok(inputs(capacity_share=[0.9, 1.0]))
        lo = self.ok(inputs(capacity_share=[0.3, 0.4]))
        self.assertGreater(lo["due_date"], hi["due_date"])

    def test_single_number_share_is_a_degenerate_range(self):
        out = self.ok(inputs(capacity_share=0.5))
        self.assertEqual(out["inputs"]["capacity_share"], [0.5, 0.5])

    def test_bad_share_refused(self):
        for bad in ([0.8, 0.4], [0, 0.5], [0.5, 1.5], "half", []):
            r = self.run_cli(inputs(capacity_share=bad))
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("capacity_share", r.stderr)

    # AC2
    def test_non_measured_factors_labelled_assumed(self):
        out = self.flat(december_factor=0.5, freezes=[{"start": "2026-12-20", "end": "2027-01-03"}], soak_weeks=2)
        by = {a["factor"]: a for a in out["assumptions"]}
        self.assertEqual(set(by), {"capacity_share", "december_factor", "freezes", "soak_weeks"})
        for a in by.values():
            self.assertEqual(a["label"], "assumed, not measured")
        self.assertEqual(by["december_factor"]["value"], 0.5)
        self.assertEqual(by["soak_weeks"]["value"], 2)

    def test_unset_factors_are_not_listed_except_share(self):
        out = self.flat()
        self.assertEqual([a["factor"] for a in out["assumptions"]], ["capacity_share"])

    # AC5
    def test_december_factor_slows_december_weeks_only(self):
        base = self.flat()
        self.assertEqual(base["likely_date"], "2026-12-14")
        slow = self.flat(december_factor=0.5)
        # Nov 23 and Nov 30 at 10; Dec 7 and Dec 14 at 5 -> done after 4 weeks.
        self.assertEqual(slow["likely_date"], "2026-12-21")

    def test_december_factor_leaves_pre_december_work_alone(self):
        out = self.ok(inputs(history=self.FLAT, capacity_share=[1, 1], remaining_points=20, december_factor=0.1))
        self.assertEqual(out["likely_date"], "2026-12-07")

    def test_december_factor_must_be_positive_number(self):
        for bad in (0, -1, "slow"):
            r = self.run_cli(inputs(december_factor=bad))
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("december_factor", r.stderr)

    # AC3 / AC4
    def prod(self, **over):
        return self.flat(**over)["production"]

    def test_no_soak_means_no_production_date_and_says_so(self):
        p = self.prod()
        self.assertIsNone(p["likely_date"])
        self.assertIsNone(p["due_date"])
        self.assertIn("no soak length", p["note"].lower())

    def test_soak_adds_weeks_to_the_finish(self):
        p = self.prod(soak_weeks=2)
        self.assertEqual(p["likely_date"], "2026-12-28")
        self.assertEqual(p["due_date"], "2026-12-28")
        self.assertIsNone(p["note"])

    def test_cutover_never_lands_inside_a_freeze(self):
        p = self.prod(soak_weeks=2, freezes=[{"start": "2026-12-20", "end": "2027-01-03", "name": "holiday"}])
        self.assertEqual(p["likely_date"], "2027-01-04")  # first day after the freeze
        self.assertEqual(p["dates"]["85"], "2027-01-04")

    def test_back_to_back_freezes_chain(self):
        p = self.prod(soak_weeks=2, freezes=[
            {"start": "2027-01-04", "end": "2027-01-10"},
            {"start": "2026-12-20", "end": "2027-01-03"},
        ])
        self.assertEqual(p["likely_date"], "2027-01-11")

    def test_freeze_boundaries_are_inclusive(self):
        p = self.prod(soak_weeks=2, freezes=[{"start": "2026-12-28", "end": "2026-12-28"}])
        self.assertEqual(p["likely_date"], "2026-12-29")

    def test_freeze_does_not_move_epic_dates(self):
        a = self.flat(soak_weeks=2)
        b = self.flat(soak_weeks=2, freezes=[{"start": "2026-12-10", "end": "2026-12-31"}])
        self.assertEqual(a["likely_date"], b["likely_date"])
        self.assertEqual(a["due_date"], b["due_date"])

    def test_freeze_outside_cutover_leaves_it_alone(self):
        p = self.prod(soak_weeks=2, freezes=[{"start": "2027-02-01", "end": "2027-02-07"}])
        self.assertEqual(p["likely_date"], "2026-12-28")

    def test_bad_freezes_refused(self):
        for bad in ([{"start": "2026-12-20"}], [{"start": "2027-01-03", "end": "2026-12-20"}], [{"start": "x", "end": "y"}], "none"):
            r = self.run_cli(inputs(freezes=bad))
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("freezes", r.stderr)

    def test_bad_soak_refused(self):
        for bad in (-1, "two", 1.5):
            r = self.run_cli(inputs(soak_weeks=bad))
            self.assertEqual(r.returncode, 2, bad)
            self.assertIn("soak_weeks", r.stderr)

    def test_chain_rows_carry_production_dates(self):
        data = inputs(scope_file=str(FIXTURES / "scope_search.json"), initiative="LV-1",
                      history=self.FLAT, capacity_share=[1, 1], soak_weeks=1,
                      freezes=[{"start": "2026-01-01", "end": "2026-01-02"}])
        del data["remaining_points"]
        out = self.ok(data)
        for row in out["chain"]:
            self.assertEqual(row["production"]["likely_date"],
                             (date.fromisoformat(row["likely_date"]) + __import__("datetime").timedelta(weeks=1)).isoformat())
        self.assertEqual(out["production"]["likely_date"], out["chain"][-1]["production"]["likely_date"])

class TestUnit(PaceCase):
    def chain_items(self, *extra, **over):
        data = inputs(scope_file=str(FIXTURES / "scope_search.json"), initiative="LV-1")
        del data["remaining_points"]
        data.update(over)
        return self.ok(data, "--unit", "items", *extra)

    def test_default_unit_is_points(self):
        out = self.ok(inputs())
        self.assertEqual(out["unit"], "points")
        self.assertEqual(self.ok(inputs(), "--unit", "points"), out)

    def test_bad_unit_refused(self):
        r = self.run_cli(inputs(), "--unit", "hours")
        self.assertNotEqual(r.returncode, 0)

    def test_items_unit_stated_in_output(self):
        out = self.ok(inputs(remaining_items=10), "--unit", "items")
        self.assertEqual(out["unit"], "items")
        self.assertEqual(out["inputs"]["remaining_items"], 10)
        self.assertNotIn("remaining_points", out["inputs"])
        self.assertIn("items", out["refresh_trigger"])

    def test_items_unit_needs_remaining_items(self):
        r = self.run_cli(inputs(), "--unit", "items")
        self.assertEqual(r.returncode, 2)
        self.assertIn("remaining_items", r.stderr)

    def test_items_pace_counts_leaf_tickets_unpointed_included(self):
        issues = [
            issue("A-1", 5, [("2026-10-06", "In Progress", "Done")]),
            issue("A-2", None, [("2026-10-07", "In Progress", "Testing")]),
            issue("A-3", 8, [("2026-10-08", "In Progress", "Canceled")], status="Canceled"),
            issue("A-4", 3, [("2026-10-06", "In Progress", "Done")], subtasks=["A-5"]),
            issue("A-5", 2, [("2026-10-06", "In Progress", "Done")], parent="A-4"),
            issue("A-6", 1, [("2026-08-25", "In Progress", "Done")]),
        ]
        out = self.ok(self.pace_inputs(issues, remaining_items=4), "--unit", "items")
        weeks = {w["week"]: w["points"] for w in out["history"]}
        self.assertEqual(weeks["2026-10-05"], 3)  # A-1, A-2, A-5
        self.assertEqual(sum(weeks.values()), 3)
        self.assertEqual(out["unpointed"], [])
        self.assertFalse(any("npointed" in w for w in out["warnings"]))

    def test_items_unit_works_when_no_ticket_is_pointed(self):
        issues = [issue("A-1", None, [("2026-10-06", "In Progress", "Done")])]
        r = self.run_cli(self.pace_inputs(issues, remaining_items=4), "--unit", "items")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_points_pace_unchanged_by_items_code(self):
        issues = [issue("A-1", 5, [("2026-10-06", "In Progress", "Done")])]
        weeks, out = self.pace(issues)
        self.assertEqual(weeks["2026-10-05"], 5)
        self.assertEqual(out["unit"], "points")

    def test_remaining_is_count_of_open_leaf_tickets(self):
        # LV-10: LV-101 open, LV-105 open unpointed (counts); LV-102 testing, done and canceled do not.
        # LV-11: LV-111 is a parent; LV-112 + LV-113. LV-12: LV-121.
        out = self.chain_items()
        rows = {r["epic"]: r for r in out["chain"]}
        self.assertEqual({k: r["remaining_items"] for k, r in rows.items()}, {"LV-12": 1, "LV-10": 2, "LV-11": 2})
        self.assertNotIn("remaining_points", rows["LV-10"])
        self.assertEqual(out["scope"]["epics"][1]["remaining_items"], 2)
        self.assertEqual(out["scope"]["not_in_the_dates_items"], 1)
        self.assertFalse(any("LV-105" in w for w in out["scope"]["warnings"]))
        self.assertEqual(out["inputs"]["remaining_items"], 5)

    def test_scope_points_still_default(self):
        data = inputs(scope_file=str(FIXTURES / "scope_search.json"))
        del data["remaining_points"]
        out = self.ok(data)
        self.assertEqual({r["epic"]: r["remaining_points"] for r in out["chain"]}, {"LV-12": 2, "LV-10": 5, "LV-11": 5})
        self.assertTrue(any("LV-105" in w for w in out["scope"]["warnings"]))

    def test_named_epic_in_items(self):
        out = self.chain_items(epic="LV-10", seed=3)
        self.assertEqual(out["inputs"]["remaining_items"], 2)
        self.assertNotIn("chain", out)

    def test_constant_pace_items_exact(self):
        hist = [{"week": f"2026-09-{d:02d}", "points": 2} for d in (7, 14, 21)]
        out = self.ok(inputs(history=hist, capacity_share=[1, 1], remaining_items=6), "--unit", "items")
        self.assertEqual(out["due_date"], "2026-12-14")

    def test_unit_can_come_from_inputs_file_and_flag_wins(self):
        out = self.ok(inputs(unit="items", remaining_items=3))
        self.assertEqual(out["unit"], "items")

    def test_flag_overrides_inputs_unit(self):
        out = self.ok(inputs(unit="items"), "--unit", "points")
        self.assertEqual(out["unit"], "points")


class TestInvocation(unittest.TestCase):
    root = FORECASTER.parent

    def test_user_invoked_only(self):
        skill = (self.root / "SKILL.md").read_text()
        self.assertIn("disable-model-invocation: true", skill.split("---")[1])
        yaml = (self.root / "agents" / "openai.yaml").read_text()
        self.assertIn("allow_implicit_invocation: false", yaml)

    def test_listed_in_bucket_readme(self):
        readme = (self.root.parent / "README.md").read_text()
        self.assertIn("[forecaster](./forecaster/SKILL.md)", readme)


if __name__ == "__main__":
    unittest.main()
