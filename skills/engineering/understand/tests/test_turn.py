#!/usr/bin/env python3
"""Hook tests for the turn-owner latch. No Claude or Cursor process is involved."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TURN = Path(__file__).resolve().parents[1] / "turn.py"


class TurnTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.home = Path(tempfile.mkdtemp())
        self.env = {**os.environ, "UNDERSTAND_HOME": str(self.home)}

    def hook(self, platform, payload):
        body = dict(payload)
        body.setdefault("workspace_roots", [str(self.root)])
        proc = subprocess.run(
            [sys.executable, str(TURN), "hook", "--platform", platform, "--tag", "turn-owner"],
            input=json.dumps(body),
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, data, proc.stdout

    def claude(self, prompt, session="abc"):
        return self.hook(
            "claude",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": session,
                "prompt": prompt,
            },
        )

    def state(self):
        return json.loads((self.root / ".claude" / "turn-owner.json").read_text())

    def text(self, data):
        return data["hookSpecificOutput"]["additionalContext"]

    def test_understand_command_latches_and_injects(self):
        code, data, _out = self.claude("/understand why two boxes")
        self.assertEqual(code, 0)
        self.assertIn("Turn owner: understand", self.text(data))
        self.assertIn("SKILL.md", self.text(data))
        self.assertEqual(self.state()["owner"], "understand")
        self.assertFalse(self.state()["pending_offer"])
        self.assertEqual(self.state()["session_key"], "claude:abc")

    def test_inline_command_latches(self):
        self.claude("Put a bookmark here. /understand why two boxes")
        self.assertEqual(self.state()["owner"], "understand")

    def test_explanation_offers_once_then_yes_latches(self):
        code, data, _out = self.claude("I still don't understand what you're asking")
        self.assertIn("Ask once", self.text(data))
        self.assertEqual(self.state()["owner"], "")
        self.assertTrue(self.state()["pending_offer"])
        code, data, _out = self.claude("yes")
        self.assertIn("Turn owner: understand", self.text(data))
        self.assertEqual(self.state()["owner"], "understand")
        self.assertFalse(self.state()["pending_offer"])

    def test_decline_answers_in_place_and_labels_layers(self):
        self.claude("explain the one-line entry")
        code, data, _out = self.claude("just tell me where the line goes")
        self.assertIn("Answer in place", self.text(data))
        self.assertIn("Ticket, Rows, Code, Theory, or Decision", self.text(data))
        self.assertEqual(self.state()["owner"], "")
        self.assertFalse(self.state()["pending_offer"])

    def test_explain_while_latched_stays_on_the_subject(self):
        self.claude("/understand the tasks")
        code, data, _out = self.claude("explain that again")
        self.assertIn("Turn owner: understand", self.text(data))
        self.assertNotIn("Ask once", self.text(data))

    def test_release_clears_the_owner(self):
        self.claude("/understand the tasks")
        code, data, out = self.claude("back to the task")
        self.assertEqual(out, "")
        self.assertIsNone(data)
        self.assertEqual(self.state()["owner"], "")

    def test_pair_owns_the_turn_and_blocks_the_offer(self):
        code, data, _out = self.claude("/pair the cutover")
        self.assertIn("Turn owner: pair", self.text(data))
        code, _data, out = self.claude("I don't understand this step")
        self.assertEqual(out, "")
        self.assertEqual(self.state()["owner"], "pair")
        self.claude("stop pairing")
        self.assertEqual(self.state()["owner"], "")

    def test_other_session_does_not_inherit_the_owner(self):
        self.claude("/understand the tasks", session="abc")
        code, data, _out = self.claude("hello", session="zzz")
        self.assertIsNone(data)
        self.assertEqual(code, 0)
        self.assertEqual(self.state()["session_key"], "claude:abc")
        self.assertEqual(self.state()["owner"], "understand")

    def test_cursor_records_the_latch_without_injecting(self):
        code, data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "beforeSubmitPrompt",
                "conversation_id": "aaa",
                "prompt": "/understand the tasks",
            },
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertIsNone(data)
        self.assertEqual(self.state()["owner"], "understand")
        self.assertEqual(self.state()["session_key"], "cursor:aaa")

    def test_session_start_reinjects_while_understand_owns_the_turn(self):
        self.claude("/understand the tasks")
        code, data, _out = self.hook(
            "claude",
            {
                "hook_event_name": "SessionStart",
                "source": "compact",
                "session_id": "abc",
            },
        )
        self.assertEqual(code, 0)
        self.assertIn("Turn owner: understand", self.text(data))

    def test_install_preserves_unrelated_hooks_and_uninstalls(self):
        settings = self.home / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(
            json.dumps(
                {
                    "hooks": {
                        "UserPromptSubmit": [
                            {"hooks": [{"type": "command", "command": "echo keep"}]}
                        ]
                    }
                }
            )
        )
        proc = subprocess.run(
            [sys.executable, str(TURN), "hooks", "install", "claude"],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        installed = json.loads(settings.read_text())
        commands = [
            item["command"]
            for group in installed["hooks"]["UserPromptSubmit"]
            for item in group["hooks"]
        ]
        self.assertIn("echo keep", commands)
        self.assertTrue(any("--tag turn-owner" in command for command in commands))
        subprocess.run(
            [sys.executable, str(TURN), "hooks", "uninstall", "claude"],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        removed = json.loads(settings.read_text())
        left = [
            item["command"]
            for group in removed["hooks"]["UserPromptSubmit"]
            for item in group["hooks"]
        ]
        self.assertEqual(left, ["echo keep"])


if __name__ == "__main__":
    unittest.main()
