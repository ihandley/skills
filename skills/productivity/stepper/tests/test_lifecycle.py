#!/usr/bin/env python3
"""Every state of a context id, driven through the CLI in one matrix.

No test here names the archive folder or its file layout. An archived context
is observed through the lifecycle module.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

STEPPER = Path(__file__).resolve().parents[1] / "stepper.py"


def load_module():
    sys.path.insert(0, str(STEPPER.parent))
    spec = importlib.util.spec_from_file_location("stepper_lifecycle_under_test", STEPPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class IdMatrix(unittest.TestCase):
    ME, OTHER = "cursor:me", "cursor:other"

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.home = Path(tempfile.mkdtemp())
        self.env = {**os.environ, "STEPPER_HOME": str(self.home)}
        self.mod = load_module()
        os.environ["STEPPER_HOME"] = str(self.home)
        self.addCleanup(os.environ.pop, "STEPPER_HOME", None)
        for key in (self.ME, self.OTHER):
            self.register(key)

    def run_cmd(self, *args):
        proc = subprocess.run([sys.executable, str(STEPPER), *args, "--root", str(self.root)],
                              text=True, capture_output=True, env=self.env, check=False)
        return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip() else None)

    def register(self, key):
        platform, ident = key.split(":")
        body = {"hook_event_name": "beforeSubmitPrompt", "prompt": "stepper, track these",
                "conversation_id": ident, "workspace_roots": [str(self.root)]}
        subprocess.run([sys.executable, str(STEPPER), "hook", "--platform", platform, "--tag", "stepper"],
                       input=json.dumps(body), text=True, capture_output=True, env=self.env, check=True)

    def capture(self, key, cid="work", item="A-1: do it"):
        return self.run_cmd("capture", "--session", key, "--context", cid, "--item", item)

    def attach(self, key, cid="work", take=False):
        return self.run_cmd("attach", "--session", key, cid, *(["--take"] if take else []))

    def archived(self, cid="work"):
        return self.mod.context_ids(self.root).archived(cid)

    def live_file(self, cid="work"):
        return self.mod.context_path(self.root, cid)

    # ---- state: free
    def test_free_id_can_be_captured(self):
        code, data = self.capture(self.ME)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["context"]["lease"]["session_key"], self.ME)

    def test_free_id_cannot_be_attached(self):
        code, data = self.attach(self.ME)
        self.assertEqual(code, 1)
        self.assertIn("no context work", data["error"])

    # ---- state: open and held by this session
    def test_held_by_me_refuses_capture_and_attach_is_a_no_op(self):
        self.capture(self.ME)
        code, data = self.capture(self.ME)
        self.assertEqual(code, 1)
        self.assertIn("already exists and is open", data["error"])
        code, data = self.attach(self.ME)
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["lease"]["session_key"], self.ME)

    # ---- state: open and held by another session
    def test_held_by_other_is_refused_until_taken(self):
        self.capture(self.ME)
        code, data = self.capture(self.OTHER)
        self.assertEqual(code, 1)
        self.assertIn("held by %s" % self.ME, data["error"])
        code, data = self.attach(self.OTHER)
        self.assertEqual(code, 1)
        self.assertIn("held by %s" % self.ME, data["error"])
        self.assertIn("--take", data["error"])
        code, data = self.attach(self.OTHER, take=True)
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["lease"]["session_key"], self.OTHER)

    # ---- state: open and unheld
    def test_open_unheld_refuses_capture_and_can_be_attached(self):
        self.capture(self.ME)
        self.run_cmd("detach", "--session", self.ME, "--context", "work")
        code, data = self.capture(self.OTHER)
        self.assertEqual(code, 1)
        self.assertIn("no session holds it", data["error"])
        code, data = self.attach(self.OTHER)
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["lease"]["session_key"], self.OTHER)

    # ---- state: closed
    def test_closed_id_cannot_be_attached(self):
        self.capture(self.ME)
        self.run_cmd("close", "--session", self.ME, "--context", "work")
        self.assertFalse(self.live_file().exists())
        code, data = self.attach(self.ME)
        self.assertEqual(code, 1)

    def test_recapturing_a_closed_id_archives_it_and_starts_clean(self):
        self.capture(self.ME, item="OLD-1: first life")
        self.run_cmd("close", "--session", self.ME, "--context", "work")
        self.assertEqual(len(self.archived()), 1)
        code, data = self.capture(self.OTHER, item="NEW-1: second life")
        self.assertEqual(code, 0, data)
        self.assertEqual([i["id"] for i in data["context"]["items"]], ["NEW-1"])
        self.assertFalse(data["context"]["closed"])
        self.assertEqual(data["context"]["lease"]["session_key"], self.OTHER)
        self.assertEqual(len(self.archived()), 1)
        self.assertEqual([i["id"] for i in self.archived()[0]["items"]], ["OLD-1"])

    # ---- state: archived
    def test_dropped_id_is_archived_and_free_to_capture_again(self):
        self.capture(self.ME)
        self.run_cmd("drop", "--session", self.ME, "--context", "work")
        self.assertEqual(len(self.archived()), 1)
        self.assertEqual(self.mod.context_ids(self.root).inspect("work", self.ME).state.value, "archived")
        code, data = self.capture(self.ME, item="NEW-1: again")
        self.assertEqual(code, 0, data)

    def test_archived_id_cannot_be_attached(self):
        self.capture(self.ME)
        self.run_cmd("drop", "--session", self.ME, "--context", "work")
        code, data = self.attach(self.ME)
        self.assertEqual(code, 1)

    # ---- state: corrupt
    def corrupt(self):
        self.capture(self.ME)
        self.live_file().write_bytes(b"{not json")

    def test_corrupt_is_reported_the_same_way_on_capture_and_on_attach(self):
        self.corrupt()
        c_code, c_data = self.capture(self.ME)
        a_code, a_data = self.attach(self.ME)
        self.assertEqual((c_code, a_code), (1, 1))
        for data in (c_data, a_data):
            self.assertIn("corrupt state at", data["error"])
            self.assertIn("left in place", data["error"])
        self.assertEqual(self.live_file().read_bytes(), b"{not json")

    def test_corrupt_is_reported_on_a_held_command_too(self):
        self.corrupt()
        code, data = self.run_cmd("verify", "--session", self.ME, "--context", "work", "A-1", "--evidence", "x")
        self.assertEqual(code, 1)
        self.assertIn("corrupt state at", data["error"])

    # ---- the module states, directly
    def test_inspect_names_each_state(self):
        ids = self.mod.context_ids(self.root)
        states = {}
        states["free"] = ids.inspect("work", self.ME).state.value
        self.capture(self.ME)
        states["mine"] = ids.inspect("work", self.ME).state.value
        states["other"] = ids.inspect("work", self.OTHER).state.value
        self.run_cmd("detach", "--session", self.ME, "--context", "work")
        states["unheld"] = ids.inspect("work", self.ME).state.value
        self.assertEqual(states, {"free": "free", "mine": "held_by_me", "other": "held_by_other",
                                  "unheld": "open_unheld"})
        self.live_file().write_bytes(b"{not json")
        self.assertEqual(ids.inspect("work", self.ME).state.value, "corrupt")


if __name__ == "__main__":
    unittest.main()
