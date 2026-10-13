#!/usr/bin/env python3
"""CLI tests for the stepper state machine. No Cursor or Claude process is involved."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

STEPPER = Path(__file__).resolve().parents[1] / "stepper.py"
AC_REPORT = """Acceptance criteria

- [x] AC-1: login works
- [x] AC-2: logout works
- [ ] AC-3: reset email is sent
- [ ] AC-4: rate limit returns 429
"""


class StepperTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.home = Path(tempfile.mkdtemp())
        self.env = {**os.environ, "STEPPER_HOME": str(self.home)}

    def cli(self, command, *args):
        proc = subprocess.run(
            [sys.executable, str(STEPPER), command, "--root", str(self.root), *args],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, data

    def hook(self, platform, payload):
        body = dict(payload)
        body["workspace_roots"] = [str(self.root)]
        proc = subprocess.run(
            [sys.executable, str(STEPPER), "hook", "--platform", platform, "--tag", "stepper"],
            input=json.dumps(body),
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, data, proc.stdout

    def register(self, session="cursor:aaa", prompt="stepper, track these", generation="g0"):
        platform, ident = session.split(":", 1)
        event = "beforeSubmitPrompt" if platform == "cursor" else "UserPromptSubmit"
        payload = {"hook_event_name": event, "prompt": prompt, "generation_id": generation}
        if platform == "cursor":
            payload["conversation_id"] = ident
        else:
            payload["session_id"] = ident
        return self.hook(platform, payload)

    def capture(self, session="cursor:aaa", context="default"):
        self.register(session)
        return self.cli(
            "capture",
            "--session",
            session,
            "--context",
            context,
            "--item",
            "AC-3: reset email is sent",
            "--item",
            "AC-4: rate limit returns 429",
        )

    def test_capture_persists_and_restores_in_a_fresh_process(self):
        code, data = self.capture()
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["items"][0]["status"], "active")
        self.assertEqual(data["context"]["lease"]["session_key"], "cursor:aaa")
        code, again = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertEqual(again["context"]["items"][1]["id"], "AC-4")
        path = self.root / ".stepper" / "contexts" / "default.json"
        self.assertTrue(path.exists())

    def test_unknown_session_is_rejected(self):
        code, data = self.cli("capture", "--session", "cursor:invented", "--item", "AC-3: x")
        self.assertEqual(code, 1)
        self.assertIn("unknown session", data["error"])
        self.assertFalse((self.root / ".stepper" / "contexts" / "default.json").exists())

    def test_second_session_cannot_mutate_or_receive_reminders(self):
        self.capture()
        self.register("cursor:bbb", prompt="stepper, what's left")
        code, data = self.cli("verify", "--session", "cursor:bbb", "AC-3", "--evidence", "sent")
        self.assertEqual(code, 1)
        self.assertIn("does not hold", data["error"])
        code, status = self.cli("status", "--session", "cursor:bbb")
        self.assertIsNone(status["context"])
        code, inventory = self.cli("status")
        self.assertEqual(inventory["contexts"][0]["lease"]["session_key"], "cursor:aaa")

    def test_attach_requires_take_for_a_live_lease(self):
        self.capture()
        self.register("cursor:bbb")
        code, denied = self.cli("attach", "--session", "cursor:bbb", "default")
        self.assertEqual(code, 1)
        self.assertIn("--take", denied["error"])
        code, taken = self.cli("attach", "--session", "cursor:bbb", "default", "--take")
        self.assertEqual(code, 0)
        self.assertEqual(taken["context"]["lease"]["session_key"], "cursor:bbb")
        code, lost = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "sent")
        self.assertEqual(code, 1)

    def test_new_session_does_not_auto_attach(self):
        self.capture()
        self.register("cursor:bbb", prompt="what is left in the repo")
        code, data = self.cli("status", "--session", "cursor:bbb")
        self.assertIsNone(data["context"])
        code, data, _out = self.hook(
            "cursor",
            {"hook_event_name": "sessionStart", "conversation_id": "bbb", "generation_id": "n1"},
        )
        self.assertEqual(code, 0)
        self.assertIsNone(data)

    def test_detach_and_session_end_keep_items(self):
        self.capture()
        before = json.loads((self.root / ".stepper" / "contexts" / "default.json").read_text())
        code, _data = self.cli("detach", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        after = json.loads((self.root / ".stepper" / "contexts" / "default.json").read_text())
        self.assertEqual(after["items"], before["items"])
        self.assertIsNone(after["lease"])
        self.cli("attach", "--session", "cursor:aaa", "default")
        code, _data, _out = self.hook(
            "cursor",
            {"hook_event_name": "sessionEnd", "conversation_id": "aaa"},
        )
        self.assertEqual(code, 0)
        ended = json.loads((self.root / ".stepper" / "contexts" / "default.json").read_text())
        self.assertEqual(ended["items"], before["items"])
        self.assertIsNone(ended["lease"])

    def test_transitions_evidence_and_duplicates(self):
        self.capture()
        code, blocked = self.cli("block", "--session", "cursor:aaa", "AC-4", "--reason", "needs provider")
        self.assertEqual(code, 1)
        code, blocked = self.cli("block", "--session", "cursor:aaa", "AC-3", "--reason", "needs provider")
        self.assertEqual(code, 0)
        self.assertEqual(blocked["context"]["items"][0]["status"], "blocked")
        code, same = self.cli("block", "--session", "cursor:aaa", "AC-3", "--reason", "needs provider")
        self.assertEqual(code, 0)
        code, changed = self.cli("block", "--session", "cursor:aaa", "AC-3", "--reason", "other")
        self.assertEqual(code, 1)
        code, _data = self.cli("unblock", "--session", "cursor:aaa", "AC-3")
        self.assertEqual(code, 0)
        code, _data = self.cli("focus", "--session", "cursor:aaa", "AC-3")
        self.assertEqual(code, 0)
        code, missing = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "   ")
        self.assertEqual(code, 1)
        self.assertIn("non-empty", missing["error"])
        code, verified = self.cli(
            "verify", "--session", "cursor:aaa", "AC-3", "--evidence", "  mailbox received the reset  "
        )
        self.assertEqual(code, 0)
        ac3 = verified["context"]["items"][0]
        self.assertEqual(ac3["status"], "verified")
        self.assertEqual(ac3["evidence"], "mailbox received the reset")
        self.assertEqual(verified["context"]["items"][1]["status"], "active")
        self.assertIn("AC-4 active", verified["reminder"])
        code, again = self.cli(
            "verify", "--session", "cursor:aaa", "AC-3", "--evidence", "mailbox received the reset"
        )
        self.assertEqual(code, 0)
        code, other = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "different")
        self.assertEqual(code, 1)
        code, _data = self.cli("focus", "--session", "cursor:aaa", "AC-4")
        self.assertEqual(code, 0)

    def test_false_evidence_is_stored_without_a_correctness_check(self):
        self.capture()
        code, data = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "this is not true")
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["items"][0]["evidence"], "this is not true")

    def test_defer_cancel_pause_and_close(self):
        self.capture()
        code, data = self.cli("defer", "--session", "cursor:aaa", "AC-4")
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["items"][1]["status"], "deferred")
        code, data = self.cli("focus", "--session", "cursor:aaa", "AC-4")
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["items"][1]["status"], "active")
        code, data = self.cli("cancel", "--session", "cursor:aaa", "AC-4")
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["items"][1]["status"], "cancelled")
        code, data = self.cli("pause", "--session", "cursor:aaa")
        self.assertTrue(data["context"]["paused"])
        code, data = self.cli("resume", "--session", "cursor:aaa")
        self.assertFalse(data["context"]["paused"])
        code, data = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "sent")
        self.assertTrue(data["context"]["complete"])
        self.assertIn("complete", data["reminder"])
        code, data = self.cli("close", "--session", "cursor:aaa")
        self.assertTrue(data["context"]["closed"])
        self.assertIsNone(data["context"]["lease"])
        self.assertEqual(data["context"]["items"][0]["status"], "verified")

    def test_multiple_contexts_do_not_overwrite(self):
        self.capture()
        code, data = self.cli(
            "capture", "--session", "cursor:aaa", "--context", "other", "--item", "AC-9: another"
        )
        self.assertEqual(code, 1)
        self.cli("detach", "--session", "cursor:aaa")
        code, data = self.cli(
            "capture", "--session", "cursor:aaa", "--context", "default", "--item", "AC-9: another"
        )
        self.assertEqual(code, 1)
        code, data = self.cli(
            "capture", "--session", "cursor:aaa", "--context", "other", "--item", "AC-9: another"
        )
        self.assertEqual(code, 0)
        self.assertTrue((self.root / ".stepper" / "contexts" / "default.json").exists())
        self.assertTrue((self.root / ".stepper" / "contexts" / "other.json").exists())

    def test_corrupt_file_is_preserved_and_not_replaced(self):
        self.capture()
        path = self.root / ".stepper" / "contexts" / "default.json"
        original = b"{not json"
        path.write_bytes(original)
        code, data = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "sent")
        self.assertEqual(code, 1)
        self.assertIn("left in place", data["error"])
        self.assertEqual(path.read_bytes(), original)
        contexts = list((self.root / ".stepper" / "contexts").glob("*.json"))
        self.assertEqual(contexts, [path])
        copies = list((self.root / ".stepper" / "quarantine").glob("*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), original)
        code, status = self.cli("status")
        self.assertEqual(code, 0)
        self.assertTrue(any(Path(item).name == "default.json" for item in status["corrupt_files"]))
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list((self.root / ".stepper" / "contexts").glob("*.json")), [path])

    def test_failed_hook_does_not_change_context_bytes(self):
        self.capture()
        path = self.root / ".stepper" / "contexts" / "default.json"
        before = path.read_bytes()
        proc = subprocess.run(
            [sys.executable, str(STEPPER), "hook", "--platform", "cursor", "--tag", "stepper"],
            input="{not json",
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(path.read_bytes(), before)

    def test_parser_ignores_checked_and_unqualified_lists(self):
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": "aaa",
                "generation_id": "g1",
                "text": "1. Open the file\n2. Read the header\n",
            },
        )
        self.assertEqual(out, "")
        self.assertFalse((self.root / ".stepper" / "suggestions.json").exists())
        self.hook(
            "cursor",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": "aaa",
                "generation_id": "g1",
                "text": AC_REPORT,
            },
        )
        code, offer, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g1",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertIn("AC-3", offer["followup_message"])
        self.assertIn("AC-4", offer["followup_message"])
        self.assertNotIn("AC-1", offer["followup_message"])

    def test_final_message_offers_once_on_stop_not_on_an_earlier_tool(self):
        self.hook(
            "cursor",
            {
                "hook_event_name": "postToolUse",
                "conversation_id": "aaa",
                "generation_id": "g1",
                "tool_name": "Shell",
            },
        )
        self.hook(
            "cursor",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": "aaa",
                "generation_id": "g1",
                "text": AC_REPORT,
            },
        )
        code, first, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g1",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertIn("followup_message", first)
        code, second, out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g1",
                "status": "completed",
                "loop_count": 1,
            },
        )
        self.assertEqual(out, "")

    def test_same_generation_tool_after_detection_injects_without_a_second_stop(self):
        self.hook(
            "cursor",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": "aaa",
                "generation_id": "g2",
                "text": AC_REPORT,
            },
        )
        code, injected, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "postToolUse",
                "conversation_id": "aaa",
                "generation_id": "g2",
                "tool_name": "Shell",
            },
        )
        self.assertIn("additional_context", injected)
        self.assertIn("Ask the user once", injected["additional_context"])
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g2",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertEqual(out, "")

    def test_decline_suppresses_the_same_hash(self):
        self.hook(
            "cursor",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": "aaa",
                "generation_id": "g3",
                "text": AC_REPORT,
            },
        )
        _code, offer, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g3",
                "status": "completed",
                "loop_count": 0,
            },
        )
        digest = offer["followup_message"].split()[2].rstrip(":")
        self.register()
        code, _data = self.cli("decline", "--session", "cursor:aaa", digest)
        self.assertEqual(code, 0)
        self.hook(
            "cursor",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": "bbb",
                "generation_id": "g4",
                "text": AC_REPORT,
            },
        )
        _code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "bbb",
                "generation_id": "g4",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertEqual(out, "")

    def test_pause_and_unrelated_question_do_not_follow_up(self):
        self.capture()
        self.cli("pause", "--session", "cursor:aaa")
        self.register("cursor:aaa", prompt="what time is it?", generation="g5")
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g5",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertEqual(out, "")
        self.cli("resume", "--session", "cursor:aaa")
        self.register("cursor:aaa", prompt="what time is it?", generation="g6")
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g6",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertEqual(out, "")

    def test_tracked_stop_reminds_once(self):
        self.capture()
        self.register("cursor:aaa", prompt="fix AC-3", generation="g7")
        code, data, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g7",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertIn("AC-3 active", data["followup_message"])
        self.assertIn("AC-4 pending", data["followup_message"])
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g7",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertEqual(out, "")

    def test_compaction_reinjects_on_the_next_tool_only(self):
        self.capture()
        self.hook("cursor", {"hook_event_name": "preCompact", "conversation_id": "aaa", "trigger": "auto"})
        code, data, _out = self.hook(
            "cursor",
            {"hook_event_name": "postToolUse", "conversation_id": "aaa", "generation_id": "g8"},
        )
        self.assertIn("AC-4 pending", data["additional_context"])
        code, _data, out = self.hook(
            "cursor",
            {"hook_event_name": "postToolUse", "conversation_id": "aaa", "generation_id": "g9"},
        )
        self.assertEqual(out, "")

    def test_platform_hooks_ignore_each_other(self):
        code, _data, out = self.hook(
            "claude",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g1",
                "loop_count": 0,
            },
        )
        self.assertEqual(out, "")

    def test_hook_install_preserves_unrelated_settings_and_uninstalls(self):
        cursor = self.home / ".cursor" / "hooks.json"
        cursor.parent.mkdir(parents=True)
        original = {
            "version": 1,
            "editor": {"formatOnSave": True},
            "hooks": {"stop": [{"command": "echo keep-me"}]},
        }
        cursor.write_text(json.dumps(original, indent=2) + "\n")
        before = cursor.read_bytes()
        code, data = self.cli_home("hooks", "install", "cursor")
        self.assertEqual(code, 0)
        installed = json.loads(cursor.read_text())
        self.assertEqual(installed["editor"], {"formatOnSave": True})
        self.assertEqual(installed["hooks"]["stop"][0]["command"], "echo keep-me")
        self.assertTrue(any("--tag stepper" in entry["command"] for entry in installed["hooks"]["stop"]))
        self.assertTrue((self.home / ".stepper" / "backups").exists())
        code, _data = self.cli_home("hooks", "uninstall", "cursor")
        self.assertEqual(code, 0)
        removed = json.loads(cursor.read_text())
        self.assertEqual(removed["editor"], original["editor"])
        self.assertEqual(removed["hooks"]["stop"], original["hooks"]["stop"])
        self.assertEqual(json.loads(cursor.read_text()), original)
        self.assertTrue(before)
        broken = self.home / ".claude" / "settings.json"
        broken.parent.mkdir(parents=True)
        broken.write_bytes(b"{not json")
        code, data = self.cli_home("hooks", "install", "claude")
        self.assertEqual(code, 1)
        self.assertEqual(broken.read_bytes(), b"{not json")

    def test_hook_install_can_remove_a_file_it_created(self):
        code, _data = self.cli_home("hooks", "install", "claude")
        self.assertEqual(code, 0)
        path = self.home / ".claude" / "settings.json"
        self.assertTrue(path.exists())
        code, _data = self.cli_home("hooks", "uninstall", "claude")
        self.assertFalse(path.exists())
        code, status = self.cli_home("hooks", "status")
        self.assertFalse(status["cursor"]["installed"])
        self.assertFalse(status["claude"]["installed"])

    def test_acceptance_criteria_lifecycle(self):
        self.hook(
            "cursor",
            {
                "hook_event_name": "beforeSubmitPrompt",
                "conversation_id": "aaa",
                "generation_id": "life",
                "prompt": "review the acceptance criteria",
            },
        )
        for _index in range(4):
            self.hook(
                "cursor",
                {
                    "hook_event_name": "postToolUse",
                    "conversation_id": "aaa",
                    "generation_id": "life",
                    "tool_name": "Shell",
                },
            )
        self.hook(
            "cursor",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": "aaa",
                "generation_id": "life",
                "text": AC_REPORT,
            },
        )
        code, offer, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "life",
                "status": "completed",
                "loop_count": 0,
            },
        )
        digest = offer["followup_message"].split()[2].rstrip(":")
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "life",
                "status": "completed",
                "loop_count": 1,
            },
        )
        self.assertEqual(out, "")
        code, captured = self.cli("capture", "--session", "cursor:aaa", "--suggestion", digest)
        self.assertEqual(code, 0)
        self.assertEqual([item["id"] for item in captured["context"]["items"]], ["AC-3", "AC-4"])
        self.assertEqual(captured["context"]["items"][0]["status"], "active")
        self.register("cursor:bbb")
        code, _data = self.cli("add", "--session", "cursor:bbb", "--item", "AC-5: no")
        self.assertEqual(code, 1)
        code, missing = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", " ")
        self.assertEqual(code, 1)
        code, verified = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "reset mail arrived")
        self.assertIn("AC-4 active", verified["reminder"])
        code, done = self.cli("verify", "--session", "cursor:aaa", "AC-4", "--evidence", "429 from the limiter")
        self.assertTrue(done["context"]["complete"])
        self.assertIn("complete", done["reminder"])
        code, restored = self.cli("status", "--session", "cursor:aaa")
        self.assertTrue(restored["context"]["complete"])

    def test_git_exclude_is_local(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        self.capture()
        exclude = subprocess.check_output(
            ["git", "-C", str(self.root), "rev-parse", "--git-path", "info/exclude"],
            text=True,
        ).strip()
        path = Path(exclude)
        if not path.is_absolute():
            path = self.root / path
        self.assertIn(".stepper/", path.read_text())

    def cli_home(self, *args):
        proc = subprocess.run(
            [sys.executable, str(STEPPER), *args],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, data


if __name__ == "__main__":
    unittest.main()
