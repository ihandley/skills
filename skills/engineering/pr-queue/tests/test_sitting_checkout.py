#!/usr/bin/env python3
"""Checks `sitting checkout` with temporary git repos, a stand-in stepper, and a stub gh.

    python3 skills/engineering/pr-queue/tests/test_sitting_checkout.py

No network and no real clone is touched. Needs Python 3.11 or newer and git on PATH.
"""

import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "sitting"
ALIASES = HERE / "fixtures" / "aliases.yaml"

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]


def git(cwd, *args):
    return subprocess.run([*GIT, *args], cwd=cwd, text=True, capture_output=True, check=True).stdout.strip()


def executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


class SittingCheckout(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.clones = tmp / "clones"
        self.clones.mkdir()
        # origin holds main and a pull request head at refs/pull/5/head
        origin = tmp / "origin.git"
        seed = tmp / "seed"
        git(tmp, "init", "--bare", "-b", "main", str(origin))
        git(tmp, "init", "-b", "main", str(seed))
        (seed / "a.txt").write_text("base\n")
        git(seed, "add", "a.txt")
        git(seed, "commit", "-m", "base")
        git(seed, "remote", "add", "origin", str(origin))
        git(seed, "push", "origin", "main")
        git(seed, "checkout", "-b", "feature")
        (seed / "a.txt").write_text("feature\n")
        git(seed, "commit", "-am", "feature")
        self.head = git(seed, "rev-parse", "HEAD")
        git(seed, "push", "origin", f"{self.head}:refs/pull/5/head")
        self.clone = self.clones / "r1"
        git(tmp, "clone", str(origin), str(self.clone))
        # gh stub answers pr view from a file; anything else fails loudly
        self.bin = tmp / "bin"
        self.bin.mkdir()
        self.pr = tmp / "pr.json"
        self.pr.write_text(json.dumps({"headRefName": "feature", "headRefOid": self.head, "baseRefName": "release-2"}))
        executable(
            self.bin / "gh",
            f"#!/bin/sh\nif [ \"$1 $2\" = 'pr view' ]; then cat {self.pr}; exit 0; fi\necho \"unexpected gh $*\" >&2\nexit 99\n",
        )
        self.set_active("https://github.com/org/r1/pull/5")
        self.aliases = tmp / "aliases.yaml"
        self.aliases.write_text(ALIASES.read_text().replace("  repos_lib:", f"  clone_roots: [{self.clones}]\n  repos_lib:"))

    def tearDown(self):
        self.tmp.cleanup()

    def set_active(self, url):
        status = {"ok": True, "context": {"id": "pr-queue", "items": [
            {"id": "done-1", "status": "verified", "completion_criteria": "Start runs qpre on https://github.com/org/r1/pull/4."},
            {"id": "x-1", "status": "active", "completion_criteria": f"Start runs qpre on {url}. Done when the user strikes the item."},
        ]}}
        stepper = Path(self.tmp.name) / "stepper.py"
        stepper.write_text(f"import sys\nprint({json.dumps(json.dumps(status))})\n")

    def run_checkout(self, aliases=None):
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}")
        return subprocess.run(
            [sys.executable, str(SCRIPT), "checkout", "--session", "claude:s", "--root", "/r",
             "--stepper", str(Path(self.tmp.name) / "stepper.py"),
             "--aliases", str(aliases or self.aliases)],
            text=True, capture_output=True, env=env, check=False,
        )

    def test_clone_ends_on_the_pull_request_head(self):
        proc = self.run_checkout()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), self.head)
        self.assertEqual(git(self.clone, "rev-parse", "--abbrev-ref", "HEAD"), "feature")

    def test_prints_the_clone_path_and_the_pull_requests_base_ref(self):
        proc = self.run_checkout()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, f"clone: {self.clone}\nbase: release-2\n")

    def test_dirty_clone_stops_and_is_left_alone(self):
        (self.clone / "a.txt").write_text("my work\n")
        before = git(self.clone, "rev-parse", "HEAD")
        proc = self.run_checkout()
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn(f"{self.clone} has uncommitted changes", proc.stderr)
        self.assertEqual(git(self.clone, "rev-parse", "HEAD"), before)
        self.assertEqual((self.clone / "a.txt").read_text(), "my work\n")

    def test_missing_clone_names_the_repository(self):
        self.set_active("https://github.com/org/nope/pull/5")
        proc = self.run_checkout()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no clone of nope under", proc.stderr)

    def test_missing_clone_roots_names_the_key(self):
        proc = self.run_checkout(aliases=ALIASES)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing clone_roots", proc.stderr)

    def test_no_active_item_stops(self):
        status = {"ok": True, "context": {"id": "pr-queue", "items": [{"id": "a", "status": "verified"}]}}
        (Path(self.tmp.name) / "stepper.py").write_text(f"print({json.dumps(json.dumps(status))})\n")
        proc = self.run_checkout()
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no active item", proc.stderr)


if __name__ == "__main__":
    unittest.main()
