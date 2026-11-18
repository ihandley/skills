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

FIXTURES = Path(__file__).resolve().parent / "fixtures"
INPUTS = {
    "initiative": "LV-1", "scope_file": str(FIXTURES / "scope_search.json"), "start_date": "2026-11-23",
    "as_of": "2026-11-18", "capacity_share": [0.5, 0.7], "december_factor": 0.6, "seed": 7, "trials": 500,
    "history": [{"week": "2026-09-07", "points": 4}, {"week": "2026-09-14", "points": 8}],
}


def real_forecast(*extra, **over) -> dict:
    """Real `forecast` output for the scope fixture, never a hand-built dict."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "i.json"
        path.write_text(json.dumps({**INPUTS, **over}))
        r = subprocess.run([sys.executable, str(FORECASTER), "forecast", "--inputs", str(path), *extra],
                           capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


FORECAST = real_forecast()
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

    def render(self, forecast=None, prose=PROSE):
        (self.dir / "f.json").write_text(json.dumps(forecast or FORECAST))
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
        for row in FORECAST["chain"]:
            self.assertIn(f"| {row['epic']} | {row['likely_date']} | {row['due_date']} |", out)
        self.assertEqual([r["epic"] for r in FORECAST["chain"]], ["LV-12", "LV-10", "LV-11"])

    def test_single_epic_forecast_gets_one_row(self):
        f = real_forecast(epic="LV-1", remaining_points=30, scope_file=None)
        out = self.ok(forecast=f)
        self.assertIn(f"| LV-1 | {f['likely_date']} | {f['due_date']} |", out)

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
        self.assertIn("Remaining work: 12 points", section)  # 2 + 5 + 5 open points in the fixture
        self.assertIn("6 points per week", section)  # mean of 4 and 8
        self.assertIn("LV-12, LV-10, LV-11", section)
        self.assertIn("2026-12-16", section)  # as_of + 28 days
        self.assertIn("Not in the dates: 3 points", section)  # LV-10 story in Testing


class TestLabels(RenderCase):
    def test_due_date_is_the_85_percent_date(self):
        out = self.ok()
        self.assertIn("Due date: the date by which 85% of runs finish.", out)
        self.assertIn("Likely date: the date by which 50% of runs finish.", out)

    def test_assumptions_labelled(self):
        out = self.ok()
        self.assertIn("capacity_share", out)
        self.assertEqual(out.count("assumed, not measured"), 2)
        self.assertIn("december_factor", out)

    def test_warnings_expiry_and_trigger_present(self):
        out = self.ok()
        self.assertIn("Short history", out)
        self.assertIn("LV-105 is open and has no points", out)
        self.assertIn("Expires 2026-12-16", out)
        self.assertIn("Rerun when the expiry date passes", out)

    def test_no_warnings_says_none(self):
        f = {**FORECAST, "warnings": [], "unpointed": [], "scope": {**FORECAST["scope"], "warnings": []}}
        self.assertIn("No data-quality warnings.", self.ok(forecast=f))

    def test_no_em_or_en_dashes_even_from_prose(self):
        out = self.ok(prose={**PROSE, "risks": "One \u2014 two \u2013 three."})
        self.assertNotIn("\u2014", out)
        self.assertNotIn("\u2013", out)


class TestUnitAndRealForecast(RenderCase):
    def test_items_unit_named_and_parked_items_counted(self):
        f = real_forecast("--unit", "items")
        out = self.ok(forecast=f)
        section = out.split("## How the dates were built")[1].split("\n## ")[0]
        self.assertIn("Remaining work: 5 items", section)
        self.assertIn("items per week", section)
        self.assertIn("Not in the dates: 1 items", section)

    def test_renders_real_forecast_output_for_a_single_epic(self):
        f = real_forecast(epic="LV-10", scope_file=None, remaining_points=60, soak_weeks=2)
        out = self.ok(forecast=f)
        self.assertIn(f"| LV-10 | {f['likely_date']} | {f['due_date']} |", out)
        self.assertIn(f["expiry"], out)

    def test_bad_forecast_file_refused(self):
        r = self.render(forecast={"nope": 1})
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
