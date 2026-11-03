#!/usr/bin/env python3
"""Checks `sitting walk` with a stand-in stepper, a stand-in qpre, a stub gh, and piped keys.

    python3 skills/engineering/pr-queue/tests/test_sitting_walk.py

No network and no terminal is touched. Needs Python 3.11 or newer.
"""

import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_sitting_strike import STEPPER  # noqa: E402

SCRIPT = HERE.parent / "scripts" / "sitting"


def executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def item(n, status):
    return {"id": f"i{n}", "description": f"line {n}", "status": status,
            "completion_criteria": f"Start runs qpre on https://github.com/org/r{n}/pull/{n}0."}


class SittingWalk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.state = self.dir / "state.json"
        self.log = self.dir / "log"
        self.log.write_text("")
        self.stepper = self.dir / "stepper.py"
        self.stepper.write_text(STEPPER % {"state": self.state, "log": self.log})
        self.outcomes = self.dir / "outcomes"
        self.outcomes.mkdir()
        self.qpre_log = self.dir / "qpre.log"
        # stand-in qpre: args logged; writes ./script-chosen outcome for the pull request, exits as told
        self.qpre = self.dir / "qpre"
        self.qpre_plan = self.dir / "plan.json"
        self.qpre_plan.write_text("{}")
        executable(self.qpre, f"""#!/usr/bin/env python3
import json, sys
url = sys.argv[1]
open("{self.qpre_log}", "a").write(url + "\\n")
org, repo, _, number = url.split("/")[-4:]
plan = json.load(open("{self.qpre_plan}")).get(url, {{"outcome": "clean", "exit": 0}})
if plan.get("outcome") is not None:
    open("{self.outcomes}/" + org + "-" + repo + "-" + number, "w").write(plan["outcome"] + "\\n")
sys.exit(plan["exit"])
""")
        self.gh_data = self.dir / "gh.json"
        self.gh_data.write_text("{}")
        self.bin = self.dir / "bin"
        self.bin.mkdir()
        executable(self.bin / "gh", f"""#!/usr/bin/env python3
import json, sys
a = sys.argv[1:]
if a[:2] != ["pr", "view"]:
    sys.stderr.write("unexpected gh " + " ".join(a)); sys.exit(99)
print(json.dumps(json.load(open("{self.gh_data}"))[a[2]]))
""")

    def tearDown(self):
        self.tmp.cleanup()

    def sitting(self, statuses):
        items = [item(n, s) for n, s in enumerate(statuses, 1)]
        self.state.write_text(json.dumps({"contexts": [
            {"id": "pr-queue", "closed": False, "lease": {"session_key": "claude:s"}, "items": items}]}))
        self.gh_data.write_text(json.dumps({f"{n}0": {"headRefOid": "h", "reviews": []} for n in range(1, len(statuses) + 1)}))

    def plan(self, n, outcome="clean", code=0):
        data = json.loads(self.qpre_plan.read_text())
        data[f"https://github.com/org/r{n}/pull/{n}0"] = {"outcome": outcome, "exit": code}
        self.qpre_plan.write_text(json.dumps(data))

    def approve(self, n, oid="h", head="h"):
        data = json.loads(self.gh_data.read_text())
        data[f"{n}0"] = {"headRefOid": head, "reviews": [
            {"state": "APPROVED", "author": {"login": "me"}, "commit": {"oid": oid}}]}
        self.gh_data.write_text(json.dumps(data))

    def walk(self, keys, *extra):
        keys_file = self.dir / "keys"
        keys_file.write_text(keys)
        env = {"PATH": f"{self.bin}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}
        return subprocess.run(
            [sys.executable, str(SCRIPT), "walk", "--session", "claude:s", "--root", "/r", "--stepper", str(self.stepper),
             "--viewer", "me", "--qpre", str(self.qpre), "--outcome-dir", str(self.outcomes), "--keys", str(keys_file), *extra],
            text=True, capture_output=True, check=False, env=env,
        )

    def statuses(self):
        return [i["status"] for i in json.loads(self.state.read_text())["contexts"][0]["items"]]

    def qpre_calls(self):
        return self.qpre_log.read_text().splitlines() if self.qpre_log.exists() else []

    def test_runs_qpre_on_the_active_items_pull_request_after_briefing_it(self):
        self.sitting(["active", "pending"])
        proc = self.walk("k")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.qpre_calls(), ["https://github.com/org/r1/pull/10"])
        self.assertTrue(proc.stdout.startswith("done: none\nleft: i1, i2\nblocked: none\nposition: 1 of 2\n"), proc.stdout)

    def test_speaks_posted_clean_and_unfinished(self):
        for written, spoken in [("posted https://x/y", "outcome: posted"), ("clean", "outcome: clean"),
                                ("partial", "outcome: unfinished"), ("unfinished 3", "outcome: unfinished"),
                                ("unposted", "outcome: unfinished")]:
            with self.subTest(written=written):
                self.sitting(["active"])
                self.plan(1, written)
                proc = self.walk("k")
                self.assertIn(spoken, proc.stdout.splitlines())

    def test_missing_outcome_is_spoken_as_missing_never_clean(self):
        self.sitting(["active"])
        self.plan(1, None)
        proc = self.walk("k")
        self.assertIn("outcome: missing outcome", proc.stdout.splitlines())
        self.assertNotIn("outcome: clean", proc.stdout)

    def test_a_stale_outcome_line_is_not_read_when_qpre_writes_none(self):
        self.sitting(["active"])
        (self.outcomes / "org-r1-10").write_text("posted https://old\n")
        self.plan(1, None)
        proc = self.walk("k")
        self.assertIn("outcome: missing outcome", proc.stdout.splitlines())

    def test_says_whether_the_latest_commit_is_approved(self):
        self.sitting(["active"])
        self.approve(1)
        self.assertIn("approved: yes", self.walk("k").stdout.splitlines())
        self.sitting(["active"])
        self.approve(1, oid="old")
        self.assertIn("approved: no", self.walk("k").stdout.splitlines())
        self.sitting(["active"])
        self.assertIn("approved: no", self.walk("k").stdout.splitlines())

    def test_s_strikes_with_outcome_and_approval_then_walks_the_next_item(self):
        self.sitting(["active", "pending"])
        self.approve(1)
        self.plan(1, "unfinished 2")
        proc = self.walk("ss")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.statuses(), ["verified", "verified"])
        first = json.loads(self.state.read_text())["contexts"][0]["items"][0]["evidence"]
        self.assertIn("unfinished", first)
        self.assertIn("approved on latest commit", first)
        self.assertEqual(len(self.qpre_calls()), 2)
        self.assertIn("done: i1\nleft: i2\nblocked: none\nposition: 2 of 2", proc.stdout)

    def test_the_walk_stops_when_no_item_is_active(self):
        self.sitting(["active"])
        proc = self.walk("s")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.statuses(), ["verified"])
        self.assertEqual(len(self.qpre_calls()), 1)
        self.assertIn("no active item", proc.stdout)

    def test_k_keeps_the_item_active_and_stops(self):
        self.sitting(["active", "pending"])
        proc = self.walk("k")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.statuses(), ["active", "pending"])
        self.assertEqual(len(self.qpre_calls()), 1)

    def test_any_other_key_asks_again(self):
        self.sitting(["active"])
        proc = self.walk("xys")
        self.assertEqual(self.statuses(), ["verified"])
        self.assertEqual(proc.stdout.count("s strike, k keep"), 3)

    def test_q_and_ctrl_c_leave_the_item_active_and_stop(self):
        for key in ("q", "\x03"):
            with self.subTest(key=key):
                self.sitting(["active", "pending"])
                proc = self.walk(key + "s")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(self.statuses(), ["active", "pending"])

    def test_running_out_of_keys_leaves_the_item_active(self):
        self.sitting(["active"])
        proc = self.walk("")
        self.assertEqual(self.statuses(), ["active"])

    def test_quitting_qpre_leaves_the_item_active_with_no_strike_prompt(self):
        for code in (1, 130, -15):
            with self.subTest(code=code):
                self.sitting(["active", "pending"])
                self.plan(1, None, code if code > 0 else 143)
                proc = self.walk("s")
                self.assertEqual(self.statuses(), ["active", "pending"])
                self.assertNotIn("s strike", proc.stdout)
                self.assertIn("qpre quit", proc.stdout)

    def test_quit_leaves_a_half_written_outcome_unread(self):
        self.sitting(["active"])
        self.plan(1, "clean", 1)
        proc = self.walk("s")
        self.assertEqual(self.statuses(), ["active"])
        self.assertNotIn("outcome: clean", proc.stdout)

    def test_no_active_item_stops(self):
        self.sitting(["verified"])
        proc = self.walk("s")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no active item", proc.stderr)
        self.assertEqual(self.qpre_calls(), [])

    def test_missing_viewer_stops(self):
        self.sitting(["active"])
        proc = subprocess.run([sys.executable, str(SCRIPT), "walk", "--session", "claude:s", "--root", "/r", "--stepper", str(self.stepper)],
                              text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("pass --viewer", proc.stderr)


if __name__ == "__main__":
    unittest.main()
