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
        self.env = {**os.environ, "HOME": str(self.home), "PAIR_HOME": str(self.home)}

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

    def latch(self):
        path = self.root / ".claude" / "turn-owner.json"
        if not path.exists():
            return {"session_key": "", "owner": "", "pending_offer": False}
        return json.loads(path.read_text())

    def text(self, data):
        return data["hookSpecificOutput"]["additionalContext"]

    def seed(self, owner, session="claude:abc"):
        path = self.root / ".claude" / "turn-owner.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"session_key": session, "owner": owner, "pending_offer": False}))

    def test_a_stored_understand_owner_stays_owned_with_the_pair_order(self):
        self.seed("understand")
        code, data, _out = self.claude("explain that again")
        self.assertEqual(code, 0)
        self.assertIn("Turn owner: pair", self.text(data))
        self.assertNotIn("Turn owner: understand", self.text(data))
        self.assertNotIn("Ask once", self.text(data))
        self.assertTrue(self.state()["owner"])

    def test_only_stop_pairing_clears_a_stored_understand_owner(self):
        self.seed("understand")
        for prompt in ("I get it", "back to the task", "i understand now", "normal mode", "drop understand"):
            code, data, _out = self.claude(prompt)
            self.assertEqual(code, 0)
            self.assertIn("Turn owner: pair", self.text(data), prompt)
            self.assertTrue(self.state()["owner"], prompt)
        code, data, out = self.claude("stop pairing")
        self.assertEqual(out, "")
        self.assertEqual(self.state()["owner"], "")

    def test_pair_command_latches_and_injects(self):
        code, data, _out = self.claude("/pair why two boxes")
        self.assertEqual(code, 0)
        self.assertIn("Turn owner: pair", self.text(data))
        self.assertIn("SKILL.md", self.text(data))
        self.assertEqual(self.state()["owner"], "pair")
        self.assertFalse(self.state()["pending_offer"])
        self.assertEqual(self.state()["session_key"], "claude:abc")

    def test_a_mention_of_pair_later_in_the_sentence_leaves_the_turn_unowned(self):
        code, data, _out = self.claude("Put a bookmark here. /pair the cutover")
        self.assertEqual(code, 0)
        self.assertIsNone(data)
        self.assertEqual(self.latch()["owner"], "")
        self.assertFalse(self.latch()["pending_offer"])

    def test_leading_whitespace_before_pair_takes_the_turn(self):
        code, data, _out = self.claude("   /pair the cutover")
        self.assertEqual(code, 0)
        self.assertIn("Turn owner: pair", self.text(data))
        self.assertEqual(self.state()["owner"], "pair")
        self.assertFalse(self.state()["pending_offer"])

    def test_a_harness_pair_command_name_takes_the_turn(self):
        code, data, _out = self.claude(
            "<command-name>/pair</command-name>\n"
            "<command-args>the cutover</command-args>"
        )
        self.assertEqual(code, 0)
        self.assertIn("Turn owner: pair", self.text(data))
        self.assertEqual(self.state()["owner"], "pair")
        self.assertFalse(self.state()["pending_offer"])

    def test_explanation_offers_once_then_yes_latches_pair(self):
        code, data, _out = self.claude("I still don't understand what you're asking")
        self.assertIn("Ask once", self.text(data))
        self.assertEqual(self.state()["owner"], "")
        self.assertTrue(self.state()["pending_offer"])
        code, data, _out = self.claude("yes")
        self.assertIn("Turn owner: pair", self.text(data))
        self.assertEqual(self.state()["owner"], "pair")
        self.assertFalse(self.state()["pending_offer"])

    def test_decline_answers_in_place_and_labels_layers(self):
        self.claude("explain the one-line entry")
        code, data, _out = self.claude("just tell me where the line goes")
        self.assertIn("Answer in place", self.text(data))
        self.assertIn("Ticket, Rows, Code, Theory, or Decision", self.text(data))
        self.assertEqual(self.state()["owner"], "")
        self.assertFalse(self.state()["pending_offer"])

    def test_pair_owns_the_turn_and_blocks_the_offer(self):
        code, data, _out = self.claude("/pair the cutover")
        self.assertIn("Turn owner: pair", self.text(data))
        code, data, _out = self.claude("I don't understand this step")
        self.assertIn("Turn owner: pair", self.text(data))
        self.assertNotIn("Ask once", self.text(data))
        self.assertEqual(self.state()["owner"], "pair")
        self.assertFalse(self.state()["pending_offer"])
        self.claude("I get it")
        self.assertEqual(self.state()["owner"], "pair")
        self.claude("stop pairing")
        self.assertEqual(self.state()["owner"], "")

    def test_other_session_does_not_inherit_the_owner(self):
        self.claude("/pair the tasks", session="abc")
        code, data, _out = self.claude("hello", session="zzz")
        self.assertIsNone(data)
        self.assertEqual(code, 0)
        self.assertEqual(self.state()["session_key"], "claude:abc")
        self.assertEqual(self.state()["owner"], "pair")

    def test_cursor_records_the_latch_without_injecting(self):
        code, data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "beforeSubmitPrompt",
                "conversation_id": "aaa",
                "prompt": "/pair the tasks",
            },
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(self.state()["owner"], "pair")
        self.assertEqual(self.state()["session_key"], "cursor:aaa")
        code, data, out = self.hook(
            "cursor",
            {"hook_event_name": "sessionStart", "conversation_id": "aaa"},
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(self.state()["owner"], "pair")

    def test_session_start_reinjects_while_pair_owns_the_turn(self):
        self.claude("/pair the tasks")
        code, data, _out = self.hook(
            "claude",
            {
                "hook_event_name": "SessionStart",
                "source": "compact",
                "session_id": "abc",
            },
        )
        self.assertEqual(code, 0)
        self.assertIn("Turn owner: pair", self.text(data))

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

    def settings(self, platform):
        rel = Path(".claude") / "settings.json" if platform == "claude" else Path(".cursor") / "hooks.json"
        return self.home / rel

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(TURN), *args], text=True, capture_output=True, env=self.env, check=False
        )

    def test_install_registers_the_claude_events_and_no_cursor_turn_hook(self):
        self.cli("hooks", "install", "claude")
        claude = json.loads(self.settings("claude").read_text())["hooks"]
        self.assertEqual(sorted(claude), ["SessionStart", "UserPromptSubmit"])
        self.assertEqual(claude["SessionStart"][0]["matcher"], "startup|resume|compact")
        self.assertNotIn("matcher", claude["UserPromptSubmit"][0])
        self.assertIn(str(TURN), claude["UserPromptSubmit"][0]["hooks"][0]["command"])
        proc = self.cli("hooks", "install", "cursor")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.settings("cursor").exists())
        self.assertFalse(json.loads(self.cli("hooks", "status").stdout)["cursor"]["installed"])

    def test_uninstall_removes_an_old_cursor_turn_hook_and_keeps_the_rest(self):
        path = self.settings("cursor")
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "hooks": {
                        "beforeSubmitPrompt": [
                            {"command": "echo keep"},
                            {"command": "python3 /old/understand/turn.py hook --platform cursor --tag turn-owner"},
                        ],
                        "sessionStart": [
                            {"command": "python3 /old/understand/turn.py hook --platform cursor --tag turn-owner"}
                        ],
                    },
                }
            )
        )
        self.assertEqual(self.cli("hooks", "uninstall", "cursor").returncode, 0)
        self.assertEqual(
            json.loads(path.read_text()),
            {"version": 1, "hooks": {"beforeSubmitPrompt": [{"command": "echo keep"}]}},
        )

    def test_reinstall_replaces_a_command_left_by_the_old_skill_path(self):
        path = self.settings("claude")
        path.parent.mkdir(parents=True)
        old = "python3 /old/understand/turn.py hook --platform claude --tag turn-owner"
        path.write_text(json.dumps({"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": old}]}]}}))
        self.cli("hooks", "install", "claude")
        commands = [
            item["command"]
            for group in json.loads(path.read_text())["hooks"]["UserPromptSubmit"]
            for item in group["hooks"]
        ]
        self.assertEqual(len(commands), 1)
        self.assertNotIn("/old/understand/", commands[0])

    def test_install_leaves_a_receipt_and_no_temp_file(self):
        self.cli("hooks", "install", "claude")
        receipt = json.loads((self.home / ".pair" / "hook-install.json").read_text())
        self.assertTrue(receipt["claude"]["created_file"])
        self.assertEqual(list(self.settings("claude").parent.glob("*.tmp")), [])

    def test_uninstall_removes_a_settings_file_the_install_created(self):
        self.cli("hooks", "install", "claude")
        self.assertTrue(self.settings("claude").exists())
        self.cli("hooks", "uninstall", "claude")
        self.assertFalse(self.settings("claude").exists())

    def test_uninstall_keeps_a_settings_file_it_did_not_create(self):
        path = self.settings("claude")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"theme": "dark"}))
        self.cli("hooks", "install", "claude")
        self.cli("hooks", "uninstall", "claude")
        self.assertEqual(json.loads(path.read_text()), {"theme": "dark"})

    def test_status_reports_installed_events(self):
        self.cli("hooks", "install", "claude")
        status = json.loads(self.cli("hooks", "status").stdout)
        self.assertTrue(status["claude"]["installed"])
        self.assertFalse(status["cursor"]["installed"])

    def test_a_settings_file_that_is_not_json_is_refused_and_left_alone(self):
        path = self.settings("claude")
        path.parent.mkdir(parents=True)
        path.write_text("{oops")
        proc = self.cli("hooks", "install", "claude")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not valid JSON", json.loads(proc.stdout)["error"])
        self.assertEqual(path.read_text(), "{oops")

    def test_host_module_matches_the_other_copies(self):
        here = TURN.parent / "hooks_host.py"
        other = TURN.parents[2] / "productivity" / "alias" / "hooks_host.py"
        self.assertEqual(here.read_text(), other.read_text())


if __name__ == "__main__":
    unittest.main()
