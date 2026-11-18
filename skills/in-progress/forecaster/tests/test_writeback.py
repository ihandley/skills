#!/usr/bin/env python3
"""CLI tests for `forecaster.py writeback`. Forecast JSON in, Jira edit descriptors out; no Jira."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

FORECASTER = Path(__file__).resolve().parents[1] / "forecaster.py"

CHAIN = {
    "epic": None,
    "likely_date": "2027-02-01",
    "due_date": "2027-03-01",
    "chain": [
        {"epic": "LV-10", "likely_date": "2026-12-14", "due_date": "2027-01-11"},
        {"epic": "LV-11", "likely_date": "2027-02-01", "due_date": "2027-03-01"},
    ],
}
SINGLE = {"epic": "LV-7", "likely_date": "2027-01-04", "due_date": "2027-02-08"}


class WritebackCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def run_cli(self, forecast, *args):
        path = self.dir / "f.json"
        path.write_text(json.dumps(forecast))
        return subprocess.run(
            [sys.executable, str(FORECASTER), "writeback", "--forecast", str(path), *args],
            capture_output=True, text=True,
        )

    def prepare(self, forecast):
        r = self.run_cli(forecast, "prepare")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class TestDryRun(WritebackCase):
    def test_lists_each_epic_with_its_due_date(self):
        r = self.run_cli(CHAIN, "--dry-run")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["edits"], [
            {"epic": "LV-10", "duedate": "2027-01-11"},
            {"epic": "LV-11", "duedate": "2027-03-01"},
        ])

    def test_emits_nothing_executable_and_no_code(self):
        r = self.run_cli(CHAIN, "--dry-run")
        out = json.loads(r.stdout)
        self.assertNotIn("descriptors", out)
        self.assertNotIn("code", out)
        self.assertNotIn("editJiraIssue", r.stdout)
        self.assertNotIn("jira.edit_issue", r.stdout)

    def test_single_epic_forecast_gets_one_edit(self):
        out = json.loads(self.run_cli(SINGLE, "--dry-run").stdout)
        self.assertEqual(out["edits"], [{"epic": "LV-7", "duedate": "2027-02-08"}])

    def test_no_dates_is_refused(self):
        r = self.run_cli({"epic": None, "chain": []}, "--dry-run")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no epic", r.stderr)


class TestConfirmGate(WritebackCase):
    def test_prepare_lists_edits_and_a_code_but_no_descriptor(self):
        out = self.prepare(CHAIN)
        self.assertEqual(len(out["edits"]), 2)
        self.assertTrue(out["code"])
        self.assertNotIn("descriptors", out)

    def test_emit_without_confirm_is_refused(self):
        r = self.run_cli(CHAIN, "emit")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")

    def test_emit_with_wrong_code_is_refused(self):
        r = self.run_cli(CHAIN, "emit", "--confirm", "nope")
        self.assertEqual(r.returncode, 2)
        self.assertIn("not confirmed", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_emit_with_code_prints_descriptors(self):
        code = self.prepare(CHAIN)["code"]
        r = self.run_cli(CHAIN, "emit", "--confirm", code)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual([d["operation"] for d in out["descriptors"]], ["jira.edit_issue"] * 2)
        self.assertEqual([d["payload"]["issueIdOrKey"] for d in out["descriptors"]], ["LV-10", "LV-11"])

    def test_code_is_stale_once_the_forecast_changes(self):
        code = self.prepare(CHAIN)["code"]
        changed = json.loads(json.dumps(CHAIN))
        changed["chain"][0]["due_date"] = "2027-01-18"
        r = self.run_cli(changed, "emit", "--confirm", code)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")


class TestDueNotLikely(WritebackCase):
    def test_edit_sets_duedate_to_the_due_date(self):
        code = self.prepare(CHAIN)["code"]
        out = json.loads(self.run_cli(CHAIN, "emit", "--confirm", code).stdout)
        fields = [d["payload"]["fields"] for d in out["descriptors"]]
        self.assertEqual(fields, [{"duedate": "2027-01-11"}, {"duedate": "2027-03-01"}])
        for likely in ("2026-12-14", "2027-02-01"):
            self.assertNotIn(likely, r_text(out))

    def test_edits_follow_the_due_level_even_when_other_levels_exist(self):
        data = json.loads(json.dumps(SINGLE))
        data["chain"] = [{"epic": "LV-7", "likely_date": "2027-01-04", "due_date": "2027-02-08",
                          "dates": {"50": "2027-01-04", "85": "2027-02-08", "95": "2027-03-01"}}]
        out = json.loads(self.run_cli(data, "--dry-run").stdout)
        self.assertEqual(out["edits"], [{"epic": "LV-7", "duedate": "2027-02-08"}])


def r_text(obj) -> str:
    return json.dumps(obj)


if __name__ == "__main__":
    unittest.main()
