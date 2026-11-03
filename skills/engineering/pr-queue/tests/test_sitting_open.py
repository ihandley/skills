#!/usr/bin/env python3
"""Checks `sitting open` with a stand-in stepper and saved GitHub and Jira input.

    python3 skills/engineering/pr-queue/tests/test_sitting_open.py

No network is touched: `gh` is a stub that fails if called, and the fetch reads
tests/fixtures/github.json. Needs Python 3.11 or newer.
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
FIXTURES = HERE / "fixtures"

STEPPER = r'''
import json, sys
args = sys.argv[1:]
state_path = "%(state)s"
state = json.load(open(state_path))
open("%(log)s", "a").write(json.dumps(args) + "\n")

def flag(name):
    return args[args.index(name) + 1] if name in args else None

def complete(ctx):
    items = ctx["items"]
    return bool(items) and all(i["status"] in ("verified", "cancelled") for i in items) and any(i["status"] == "verified" for i in items)

def brief(ctx):
    items = ctx["items"]
    held = next((i for i in items if i["status"] in ("active", "blocked")), None)
    position = "none" if held is None else "%%d of %%d" %% (items.index(held) + 1, len(items))
    ids = lambda *s: [i["id"] for i in items if i["status"] in s]
    return {"done": ids("verified"), "left": ids("pending", "active", "deferred"), "blocked": ids("blocked"), "position": position}

def find(name):
    return next((c for c in state["contexts"] if c["id"] == name and not c["closed"]), None)

cmd = args[0]
ctx = find(flag("--context")) if flag("--context") else None
if cmd == "status" and flag("--session") is None:
    out = {"ok": True, "contexts": [{"id": c["id"], "closed": False, "lease": c["lease"], "complete": complete(c)} for c in state["contexts"] if not c["closed"]]}
elif cmd == "status":
    mine = [c for c in state["contexts"] if not c["closed"] and (c["lease"] or {}).get("session_key") == flag("--session")]
    held = next((c for c in mine if c["id"] == "pr-queue"), None)
    out = {"ok": True, "context": held, "brief": brief(held) if held else None}
elif cmd == "attach":
    ctx["lease"] = {"session_key": flag("--session")}
    out = {"ok": True, "brief": brief(ctx)}
elif cmd == "close":
    ctx["closed"] = True
    out = {"ok": True, "brief": brief(ctx)}
elif cmd == "capture":
    items = []
    for raw in [args[i + 1] for i, a in enumerate(args) if a == "--item"]:
        item_id, text, criteria = [p.strip() for p in raw.split("|", 2)]
        items.append({"id": item_id, "description": text, "completion_criteria": criteria, "status": "pending"})
    items[0]["status"] = "active"
    state["contexts"] = [c for c in state["contexts"] if c["id"] != flag("--context") or c["closed"]]
    state["contexts"].append({"id": flag("--context"), "closed": False, "lease": {"session_key": flag("--session")}, "items": items})
    out = {"ok": True}
else:
    out = {"ok": True}
json.dump(state, open(state_path, "w"))
print(json.dumps(out))
'''


def item(item_id, status):
    return {"id": item_id, "description": f"line for {item_id}", "completion_criteria": "c", "status": status}


class SittingOpen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.state = tmp / "state.json"
        self.log = tmp / "log"
        self.log.write_text("")
        (tmp / "stepper.py").write_text(STEPPER % {"state": self.state, "log": self.log})
        self.bin = tmp / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text("#!/bin/sh\necho 'gh was called' >&2\nexit 99\n")
        gh.chmod(gh.stat().st_mode | stat.S_IEXEC)
        self.contexts([])

    def tearDown(self):
        self.tmp.cleanup()

    def contexts(self, contexts):
        self.state.write_text(json.dumps({"contexts": contexts}))

    def sitting(self, statuses, holder="claude:s", name="pr-queue"):
        lease = {"session_key": holder} if holder else None
        return {"id": name, "closed": False, "lease": lease, "items": [item(f"i{n}", s) for n, s in enumerate(statuses, 1)]}

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def verbs(self):
        return [call[0] for call in self.calls() if call[0] != "status"]

    def run_open(self):
        env = dict(os.environ, TZ="UTC", PATH=f"{self.bin}:{os.environ['PATH']}")
        return subprocess.run(
            [sys.executable, str(SCRIPT), "open", "--session", "claude:s", "--root", "/r",
             "--stepper", str(Path(self.tmp.name) / "stepper.py"),
             "--viewer", "ian", "--aliases", str(FIXTURES / "aliases.yaml"),
             "--github-fixture", str(FIXTURES / "github.json"), "--today", "2026-10-28"],
            input=(FIXTURES / "jira.txt").read_text(), text=True, capture_output=True, env=env, check=False,
        )

    def brief_lines(self, proc):
        return [line for line in proc.stdout.splitlines() if line.split(":")[0] in ("done", "left", "blocked", "position")]

    def test_no_sitting_fetches_prints_the_queue_then_the_four_brief_parts(self):
        proc = self.run_open()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        queue = (FIXTURES / "normal.txt").read_text()
        self.assertTrue(proc.stdout.startswith(queue), proc.stdout)
        tail = proc.stdout[len(queue):].splitlines()
        self.assertEqual([line.split(":")[0] for line in tail], ["done", "left", "blocked", "position"])
        self.assertIn("capture", self.verbs())
        self.assertNotIn("pr-queue brief", proc.stderr)

    def test_the_brief_comes_from_a_brief_state_change_not_the_store(self):
        proc = self.run_open()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--brief", self.calls()[-1])
        self.assertNotEqual(self.calls()[-1][0], "status")

    def test_unfinished_sitting_in_this_chat_stays_and_nothing_is_fetched(self):
        self.contexts([self.sitting(["verified", "active", "pending"])])
        proc = self.run_open()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("capture", self.verbs())
        self.assertNotIn("close", self.verbs())
        self.assertNotIn("gh was called", proc.stderr)
        self.assertEqual(proc.stdout.splitlines()[:2], ["line for i2", "line for i3"])
        self.assertEqual(self.brief_lines(proc), ["done: i1", "left: i2, i3", "blocked: none", "position: 2 of 3"])

    def test_unfinished_sitting_nobody_holds_is_attached_without_a_fetch(self):
        self.contexts([self.sitting(["active", "pending"], holder=None)])
        proc = self.run_open()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("attach", self.verbs())
        self.assertNotIn("capture", self.verbs())
        self.assertNotIn("close", self.verbs())

    def test_finished_sitting_this_chat_holds_is_closed_and_captured_again(self):
        self.contexts([self.sitting(["verified", "cancelled"])])
        proc = self.run_open()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        verbs = self.verbs()
        self.assertLess(verbs.index("close"), verbs.index("capture"))
        self.assertNotIn("line for i1", proc.stdout)

    def test_finished_sitting_nobody_holds_is_attached_then_closed_then_captured(self):
        self.contexts([self.sitting(["verified"], holder=None)])
        proc = self.run_open()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        verbs = self.verbs()
        self.assertLess(verbs.index("attach"), verbs.index("close"))
        self.assertLess(verbs.index("close"), verbs.index("capture"))

    def test_sitting_another_chat_holds_stops_and_names_that_chat(self):
        self.contexts([self.sitting(["active"], holder="claude:other")])
        proc = self.run_open()
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stdout, "")
        self.assertIn("claude:other", proc.stderr)
        self.assertEqual(self.verbs(), [])

    def test_blocked_or_deferred_item_leaves_the_sitting_in_place(self):
        for statuses in (["verified", "blocked"], ["verified", "deferred"]):
            with self.subTest(statuses=statuses):
                self.log.write_text("")
                self.contexts([self.sitting(statuses)])
                proc = self.run_open()
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertNotIn("capture", self.verbs())
                self.assertNotIn("close", self.verbs())

    def test_a_finished_context_with_another_name_stays_leased(self):
        self.contexts([self.sitting(["verified"], name="other"), self.sitting(["active"], name="mine", holder="claude:s")])
        proc = self.run_open()
        self.assertEqual(proc.returncode, 0, proc.stderr)
        touched = {call[call.index("--context") + 1] for call in self.calls() if "--context" in call and call[0] in ("close", "attach")}
        self.assertNotIn("other", touched)
        self.assertNotIn("mine", touched)
        state = json.loads(self.state.read_text())
        self.assertEqual([c["closed"] for c in state["contexts"] if c["id"] in ("other", "mine")], [False, False])
        self.assertIn("capture", self.verbs())

    def test_missing_session_stops(self):
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}")
        proc = subprocess.run([sys.executable, str(SCRIPT), "open", "--root", "/r", "--stepper", "x"], text=True, capture_output=True, env=env)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("pass --session", proc.stderr)


if __name__ == "__main__":
    unittest.main()
