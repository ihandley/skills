#!/usr/bin/env python3
"""Checks the printed queue from saved input. No GitHub or Jira call is made.

    python3 skills/engineering/pr-queue/tests/test_pr_queue.py

Needs Python 3.11 or newer.
"""

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "pr-queue"
FIXTURES = HERE / "fixtures"
TODAY = "2026-10-28"


class PrQueueOutput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bin = tempfile.TemporaryDirectory()
        gh = Path(cls.bin.name) / "gh"
        gh.write_text("#!/bin/sh\necho 'gh was called' >&2\nexit 99\n")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)

    @classmethod
    def tearDownClass(cls):
        cls.bin.cleanup()

    def run_script(self, *flags, stdin="", aliases=None):
        env = dict(os.environ, TZ="UTC", PATH=f"{self.bin.name}:{os.environ['PATH']}")
        return subprocess.run(
            [
                sys.executable, str(SCRIPT),
                "--viewer", "ian",
                "--aliases", str(aliases or FIXTURES / "aliases.yaml"),
                "--github-fixture", str(FIXTURES / "github.json"),
                "--today", TODAY,
                *flags,
            ],
            input=stdin, text=True, capture_output=True, env=env, check=False,
        )

    def test_normal_list(self):
        proc = self.run_script(stdin=(FIXTURES / "jira.txt").read_text())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, (FIXTURES / "normal.txt").read_text())

    def test_marks_show_a_gone_author_a_conflict_and_failing_checks(self):
        proc = self.run_script(stdin=(FIXTURES / "jira.txt").read_text())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        for ref, marks in [
            ("r1#18", "gone"),
            ("r1#19", "conflict"),
            ("r1#20", "red"),
            ("r1#21", "gone conflict red"),
        ]:
            line = next(l for l in lines if l.startswith(ref + " "))
            self.assertTrue(line.startswith(f"{ref} {marks} · "), line)
        healthy = next(l for l in lines if l.startswith("r1#22 "))
        self.assertTrue(healthy.startswith("r1#22 · healthy · "), healthy)

    def test_normal_count_covers_the_daily_repos_older_than_seven_days(self):
        proc = self.run_script("--print-queries")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "is:pr is:open updated:<2026-10-21 repo:org/r1\n")

    def test_all_count_adds_the_other_repo_lists(self):
        proc = self.run_script("--all", "--print-queries")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout,
            "is:pr is:open updated:<2026-10-21 repo:org/r1 repo:org/lib1\n",
        )

    def test_backlog_sends_no_count_query(self):
        proc = self.run_script("--backlog", "--print-queries")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, "")

    def test_print_jql_prints_the_site_and_the_query(self):
        proc = self.run_script("--print-jql")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout,
            "cloud_id=00000000-0000-0000-0000-000000000000\n"
            "site=https://example.atlassian.net\n"
            'jql=project = JET AND "Tech Domain[Dropdown]" in ("Backend - Admin", "Edge Cloud Platform (ECP)")'
            ' AND status = "In Review" AND sprint in openSprints() ORDER BY Rank ASC\n',
        )

    def test_print_jql_names_a_missing_cloud_id(self):
        with tempfile.TemporaryDirectory() as directory:
            aliases = Path(directory) / "aliases.yaml"
            lines = (FIXTURES / "aliases.yaml").read_text().splitlines()
            aliases.write_text("\n".join(l for l in lines if "atlassian_cloud_id" not in l) + "\n")
            proc = self.run_script("--print-jql", aliases=aliases)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("missing atlassian_cloud_id", proc.stderr)
        self.assertIn("atlassian_cloud_id:", proc.stderr)

    def test_backlog_table(self):
        proc = self.run_script("--backlog")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, (FIXTURES / "backlog.txt").read_text())


if __name__ == "__main__":
    unittest.main()
