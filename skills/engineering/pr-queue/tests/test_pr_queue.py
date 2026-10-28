#!/usr/bin/env python3
"""Checks the printed queue from saved input. No GitHub or Jira call is made.

    python3 skills/engineering/pr-queue/tests/test_pr_queue.py

Needs Ruby 2.6 or newer on PATH.
"""

import os
import stat
import subprocess
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

    def run_script(self, *flags, stdin=""):
        env = dict(os.environ, TZ="UTC", PATH=f"{self.bin.name}:{os.environ['PATH']}")
        return subprocess.run(
            [
                "ruby", str(SCRIPT),
                "--viewer", "ian",
                "--aliases", str(FIXTURES / "aliases.yaml"),
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

    def test_backlog_table(self):
        proc = self.run_script("--backlog")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, (FIXTURES / "backlog.txt").read_text())


if __name__ == "__main__":
    unittest.main()
