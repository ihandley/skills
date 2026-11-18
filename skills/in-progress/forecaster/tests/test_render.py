#!/usr/bin/env python3
"""CLI tests for `forecaster.py render`. Forecast JSON in, markdown out; no Jira."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FORECASTER = Path(__file__).resolve().parents[1] / "forecaster.py"
SECTIONS = ("deferred_scope", "waits_outside_the_plan", "risks", "asks_of_manager")

FORECAST = {
    "epic": None,
    "unit": "points",
    "likely_date": "2027-02-01",
    "likely_percentile": 50,
    "due_date": "2027-03-01",
    "due_percentile": 85,
    "expiry": "2026-12-21",
    "refresh_trigger": "Rerun when the expiry date passes.",
    "assumptions": [
        {"factor": "capacity_share", "value": [0.5, 0.7], "label": "assumed, not measured"},
        {"factor": "december_factor", "value": 0.6, "label": "assumed, not measured"},
    ],
    "history": [{"week": "2026-09-07", "points": 4}, {"week": "2026-09-14", "points": 8}],
    "warnings": ["History has 2 weeks; percentiles are weak."],
    "unpointed": ["LV-9"],
    "production": {"likely_date": None, "due_date": None, "dates": {}, "note": "No soak."},
    "inputs": {"remaining_points": 30, "start_date": "2026-11-23", "capacity_share": [0.5, 0.7]},
    "chain": [
        {"epic": "LV-10", "remaining_points": 10, "likely_date": "2026-12-14", "due_date": "2027-01-11"},
        {"epic": "LV-11", "remaining_points": 20, "likely_date": "2027-02-01", "due_date": "2027-03-01"},
    ],
    "scope": {
        "warnings": ["LV-105 is open and has no points."],
        "not_in_the_dates": {"LV-10": 3},
    },
}
PROSE = {
    "title": "LVCore K8s plan",
    "deferred_scope": "Multi-region failover is deferred.",
    "waits_outside_the_plan": ["Platform team must provision the cluster.", "Security review."],
    "risks": "Pace is based on two weeks.",
    "asks_of_manager": "Protect half my time for January.",
}


class RenderCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def render(self, forecast=FORECAST, prose=PROSE):
        (self.dir / "f.json").write_text(json.dumps(forecast))
        (self.dir / "p.json").write_text(json.dumps(prose))
        return subprocess.run(
            [sys.executable, str(FORECASTER), "render", "--forecast", str(self.dir / "f.json"),
             "--prose", str(self.dir / "p.json")],
            capture_output=True, text=True,
        )

    def ok(self, **kw):
        r = self.render(**kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout


class TestDatesTable(RenderCase):
    def test_one_row_per_epic_with_likely_and_due(self):
        out = self.ok()
        self.assertIn("| Epic | Likely date | Due date |", out)
        self.assertIn("| LV-10 | 2026-12-14 | 2027-01-11 |", out)
        self.assertIn("| LV-11 | 2027-02-01 | 2027-03-01 |", out)

    def test_single_epic_forecast_gets_one_row(self):
        f = {k: v for k, v in FORECAST.items() if k not in ("chain", "scope")}
        f["epic"] = "LV-1"
        out = self.ok(forecast=f)
        self.assertIn("| LV-1 | 2027-02-01 | 2027-03-01 |", out)

    def test_title_used(self):
        self.assertTrue(self.ok().startswith("# LVCore K8s plan\n"))


class TestProse(RenderCase):
    def test_four_sections_with_text(self):
        out = self.ok()
        for heading in ("## Deferred scope", "## Waits outside the plan", "## Risks", "## Asks of the manager"):
            self.assertIn(heading, out)
        self.assertIn("Multi-region failover is deferred.", out)
        self.assertIn("- Platform team must provision the cluster.", out)
        self.assertIn("- Security review.", out)

    def test_missing_section_refused_by_name(self):
        for name in SECTIONS:
            prose = {k: v for k, v in PROSE.items() if k != name}
            r = self.render(prose=prose)
            self.assertEqual(r.returncode, 2, name)
            self.assertIn(name, r.stderr)
            self.assertEqual(r.stdout, "")

    def test_empty_section_refused(self):
        for empty in ("", "   ", [], [" "]):
            r = self.render(prose={**PROSE, "risks": empty})
            self.assertEqual(r.returncode, 2, repr(empty))
            self.assertIn("risks", r.stderr)


class TestHowBuilt(RenderCase):
    def test_states_remaining_pace_order_and_review_date(self):
        out = self.ok()
        section = out.split("## How the dates were built")[1].split("\n## ")[0]
        self.assertIn("30 points", section)
        self.assertIn("6 points per week", section)  # mean of 4 and 8
        self.assertIn("LV-10, LV-11", section)
        self.assertIn("2026-12-21", section)
        self.assertIn("3 points", section)  # not in the dates


class TestLabels(RenderCase):
    def test_due_date_is_the_85_percent_date(self):
        out = self.ok()
        self.assertIn("Due date: the date by which 85% of runs finish.", out)
        self.assertIn("Likely date: the date by which 50% of runs finish.", out)

    def test_assumptions_labelled(self):
        out = self.ok()
        self.assertIn("capacity_share", out)
        self.assertEqual(out.count("assumed, not measured"), 2)

    def test_warnings_expiry_and_trigger_present(self):
        out = self.ok()
        self.assertIn("History has 2 weeks; percentiles are weak.", out)
        self.assertIn("LV-105 is open and has no points.", out)
        self.assertIn("LV-9", out)
        self.assertIn("Expires 2026-12-21", out)
        self.assertIn("Rerun when the expiry date passes.", out)

    def test_no_warnings_says_none(self):
        f = {**FORECAST, "warnings": [], "unpointed": [], "scope": {"warnings": [], "not_in_the_dates": {}}}
        self.assertIn("No data-quality warnings.", self.ok(forecast=f))

    def test_no_em_or_en_dashes_even_from_prose(self):
        out = self.ok(prose={**PROSE, "risks": "One \u2014 two \u2013 three."})
        self.assertNotIn("\u2014", out)
        self.assertNotIn("\u2013", out)


class TestUnitAndRealForecast(RenderCase):
    def test_items_unit_named(self):
        f = {**FORECAST, "unit": "items", "inputs": {"remaining_items": 7},
             "chain": [{"epic": "LV-10", "remaining_items": 7, "likely_date": "a", "due_date": "b"}],
             "scope": {"warnings": [], "not_in_the_dates": {}}}
        out = self.ok(forecast=f)
        self.assertIn("7 items", out)
        self.assertIn("items per week", out)

    def test_renders_real_forecast_output(self):
        inputs = {
            "epic": "LV-1", "remaining_points": 60, "start_date": "2026-11-23",
            "capacity_share": [0.5, 0.7], "seed": 7, "trials": 500, "soak_weeks": 2,
            "history": [{"week": "2026-09-07", "points": 5}, {"week": "2026-09-14", "points": 13}],
        }
        (self.dir / "i.json").write_text(json.dumps(inputs))
        fc = subprocess.run([sys.executable, str(FORECASTER), "forecast", "--inputs", str(self.dir / "i.json")],
                            capture_output=True, text=True, check=True)
        data = json.loads(fc.stdout)
        out = self.ok(forecast=data)
        self.assertIn(f"| LV-1 | {data['likely_date']} | {data['due_date']} |", out)
        self.assertIn(data["expiry"], out)

    def test_bad_forecast_file_refused(self):
        r = self.render(forecast={"nope": 1})
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
