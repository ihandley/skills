#!/usr/bin/env python3
"""Checks `sitting strike` and `sitting brief` with a stand-in stepper.

    python3 skills/engineering/pr-queue/tests/test_sitting_strike.py

No network is touched. Needs Ruby 2.6 or newer.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "sitting"

STEPPER = r'''
import json, sys
args = sys.argv[1:]
state_path = "%(state)s"
state = json.load(open(state_path))
open("%(log)s", "a").write(json.dumps(args) + "\n")

def flag(name):
    return args[args.index(name) + 1] if name in args else None

def brief(ctx):
    items = ctx["items"]
    held = next((i for i in items if i["status"] in ("active", "blocked")), None)
    position = "none" if held is None else "%%d of %%d" %% (items.index(held) + 1, len(items))
    ids = lambda *s: [i["id"] for i in items if i["status"] in s]
    return {"done": ids("verified"), "left": ids("pending", "active", "deferred"), "blocked": ids("blocked"), "position": position}

wanted = flag("--context")
ctx = next((c for c in state["contexts"] if (c["lease"] or {}).get("session_key") == flag("--session") and not c["closed"] and wanted in (None, c["id"])), None)
cmd = args[0]
if ctx is None:
    print(json.dumps({"ok": False, "error": "no sitting"}))
    sys.exit(1)
if cmd == "status":
    out = {"ok": True, "context": ctx, "brief": brief(ctx)}
elif cmd == "verify":
    item = next(i for i in ctx["items"] if i["id"] == args[args.index("--context") + 2])
    item["status"] = "verified"
    item["evidence"] = flag("--evidence")
    nxt = next((i for i in ctx["items"] if i["status"] == "pending"), None)
    if nxt:
        nxt["status"] = "active"
    out = {"ok": True, "brief": brief(ctx)}
    if "--brief" not in args:
        out["context"] = ctx
else:
    out = {"ok": True}
json.dump(state, open(state_path, "w"))
print(json.dumps(out))
'''


def item(item_id, status):
    return {"id": item_id, "description": f"line for {item_id}", "completion_criteria": "c", "status": status}


class SittingStrike(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.state = tmp / "state.json"
        self.log = tmp / "log"
        self.log.write_text("")
        self.stepper = tmp / "stepper.py"
        self.stepper.write_text(STEPPER % {"state": self.state, "log": self.log})

    def tearDown(self):
        self.tmp.cleanup()

    def sitting(self, statuses, holder="claude:s"):
        items = [item(f"i{n}", s) for n, s in enumerate(statuses, 1)]
        self.state.write_text(json.dumps({"contexts": [
            {"id": "pr-queue", "closed": False, "lease": {"session_key": holder}, "items": items}]}))

    def with_other_context_first(self):
        data = json.loads(self.state.read_text())
        other = {"id": "other-skill", "closed": False, "lease": {"session_key": "claude:s"},
                 "items": [item("x1", "active"), item("x2", "pending")]}
        data["contexts"].insert(0, other)
        self.state.write_text(json.dumps(data))

    def sitting_cmd(self, command, *extra):
        return subprocess.run(
            ["ruby", str(SCRIPT), command, "--session", "claude:s", "--root", "/r", "--stepper", str(self.stepper), *extra],
            text=True, capture_output=True, check=False,
        )

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_strike_verifies_the_active_item_with_the_evidence_given(self):
        self.sitting(["active", "pending"])
        proc = self.sitting_cmd("strike", "--evidence", "posted; approved on latest commit")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        state = json.loads(self.state.read_text())
        first = state["contexts"][0]["items"][0]
        self.assertEqual(first["status"], "verified")
        self.assertEqual(first["evidence"], "posted; approved on latest commit")

    def test_strike_prints_the_next_items_four_brief_parts_and_only_those(self):
        self.sitting(["active", "pending", "pending"])
        proc = self.sitting_cmd("strike", "--evidence", "e")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), ["done: i1", "left: i2, i3", "blocked: none", "position: 2 of 3"])

    def test_strike_and_brief_use_the_pr_queue_sitting_when_the_session_holds_another_context(self):
        self.sitting(["active", "pending"])
        self.with_other_context_first()
        brief = self.sitting_cmd("brief")
        self.assertIn("position: 1 of 2", brief.stdout)
        self.assertIn("left: i1, i2", brief.stdout)
        proc = self.sitting_cmd("strike", "--evidence", "e")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        verify = next(c for c in self.calls() if c[0] == "verify")
        self.assertEqual(verify[verify.index("--context") + 2], "i1")

    def test_strike_asks_stepper_for_the_brief_form_not_the_store(self):
        self.sitting(["active", "pending"])
        proc = self.sitting_cmd("strike", "--evidence", "e")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        verify = [call for call in self.calls() if call[0] == "verify"]
        self.assertEqual(len(verify), 1)
        self.assertIn("--brief", verify[0])
        self.assertNotIn("context", proc.stdout)
        self.assertNotIn("completion_criteria", proc.stdout)

    def test_strike_on_the_last_item_prints_position_none(self):
        self.sitting(["verified", "active"])
        proc = self.sitting_cmd("strike", "--evidence", "e")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), ["done: i1, i2", "left: none", "blocked: none", "position: none"])

    def test_strike_without_evidence_stops_and_verifies_nothing(self):
        self.sitting(["active", "pending"])
        proc = self.sitting_cmd("strike")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("pass --evidence", proc.stderr)
        self.assertEqual(self.calls(), [])

    def test_strike_with_no_active_item_stops(self):
        self.sitting(["verified", "blocked"])
        proc = self.sitting_cmd("strike", "--evidence", "e")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no active item", proc.stderr)
        self.assertNotIn("verify", [call[0] for call in self.calls()])

    def test_brief_prints_the_four_parts_without_changing_anything(self):
        self.sitting(["verified", "active", "blocked"])
        before = self.state.read_text()
        proc = self.sitting_cmd("brief")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.splitlines(), ["done: i1", "left: i2", "blocked: i3", "position: 2 of 3"])
        self.assertEqual(self.state.read_text(), before)

    def test_missing_session_stops(self):
        proc = subprocess.run(["ruby", str(SCRIPT), "strike", "--root", "/r", "--stepper", "x", "--evidence", "e"],
                              text=True, capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("pass --session", proc.stderr)


if __name__ == "__main__":
    unittest.main()
