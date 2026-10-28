#!/usr/bin/env python3
"""CLI tests for the stepper state machine. No Cursor or Claude process is involved."""

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
        self.store = self.home / ".stepper"
        self.env = {**os.environ, "STEPPER_HOME": str(self.home)}

    def cli(self, command, *args):
        named = {
            "capture",
            "add",
            "focus",
            "verify",
            "block",
            "unblock",
            "defer",
            "cancel",
            "pause",
            "resume",
            "close",
            "skip",
            "free",
            "order",
            "replace",
            "drop",
            "detach",
        }
        prefix = []
        if command in named and "--context" not in args:
            prefix = ["--context", "default"]
        proc = subprocess.run(
            [sys.executable, str(STEPPER), command, "--root", str(self.root), *prefix, *args],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, data

    def hook(self, platform, payload, workspace=True):
        body = dict(payload)
        if workspace:
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

    def archived_contexts(self, context_id):
        sys.path.insert(0, str(STEPPER.parent))
        spec = importlib.util.spec_from_file_location("stepper_for_archive", STEPPER)
        mod = importlib.util.module_from_spec(spec)
        os.environ["STEPPER_HOME"] = str(self.home)
        self.addCleanup(os.environ.pop, "STEPPER_HOME", None)
        spec.loader.exec_module(mod)
        return mod.context_ids(self.root).archived(context_id)

    def git_repo(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "tracked.txt").write_text("x\n")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=t", "-c", "user.email=t@t",
                        "commit", "-q", "-m", "init"], check=True)
        return (self.root / ".git" / "info" / "exclude").read_text() if (self.root / ".git" / "info" / "exclude").exists() else ""

    def snapshot(self):
        return sorted(str(p.relative_to(self.home)) for p in self.home.rglob("*"))

    def test_an_unrelated_prompt_creates_no_store_and_leaves_the_tree_alone(self):
        exclude = self.git_repo()
        before_home = self.snapshot()
        code, _, out = self.hook("claude", {"hook_event_name": "UserPromptSubmit",
                                            "session_id": "zzz", "prompt": "how do I rebase?"})
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "")
        self.assertFalse(self.store.exists(), self.snapshot())
        self.assertEqual(self.snapshot(), before_home)
        status = subprocess.run(["git", "-C", str(self.root), "status", "--porcelain"],
                                text=True, capture_output=True, check=True).stdout
        self.assertEqual(status, "")
        exclude_path = self.root / ".git" / "info" / "exclude"
        self.assertEqual(exclude_path.read_text() if exclude_path.exists() else "", exclude)

    def test_other_events_with_nothing_to_persist_create_no_store(self):
        self.git_repo()
        payloads = [
            {"hook_event_name": "PostToolUse", "session_id": "zzz"},
            {"hook_event_name": "Stop", "session_id": "zzz", "last_assistant_message": "done"},
            {"hook_event_name": "SessionStart", "session_id": "zzz", "source": "startup"},
            {"hook_event_name": "SessionEnd", "session_id": "zzz"},
            {"hook_event_name": "PreCompact", "session_id": "zzz"},
        ]
        for payload in payloads:
            with self.subTest(event=payload["hook_event_name"]):
                self.hook("claude", payload)
                self.assertFalse(self.store.exists(), self.snapshot())

    def test_a_prompt_stepper_owns_does_create_the_store(self):
        self.git_repo()
        self.register("claude:zzz")
        self.assertTrue((self.store / "sessions").is_dir())

    def test_capture_persists_and_restores_in_a_fresh_process(self):
        code, data = self.capture()
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["items"][0]["status"], "active")
        self.assertEqual(data["context"]["lease"]["session_key"], "cursor:aaa")
        code, again = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertEqual(again["context"]["items"][1]["id"], "AC-4")
        path = self.store / "contexts" / "default.json"
        self.assertTrue(path.exists())
        self.assertFalse((self.root / ".stepper").exists())
        self.assertIsNone(data["context"]["repo"])

    def test_unknown_session_is_rejected(self):
        code, data = self.cli("capture", "--session", "cursor:invented", "--item", "AC-3: x")
        self.assertEqual(code, 1)
        self.assertIn("unknown session", data["error"])
        self.assertFalse((self.store / "contexts" / "default.json").exists())

    def test_commands_from_another_directory_use_the_injected_root(self):
        self.register("claude:sess", prompt="track these with stepper")
        other = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init"], cwd=other, check=True, capture_output=True)
        proc = subprocess.run(
            [
                sys.executable,
                str(STEPPER),
                "status",
                "--session",
                "claude:sess",
                "--root",
                str(self.root),
            ],
            cwd=other,
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        status = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(status["session"]["session_key"], "claude:sess")
        self.assertFalse((other / ".stepper").exists())
        proc = subprocess.run(
            [
                sys.executable,
                str(STEPPER),
                "capture",
                "--session",
                "claude:sess",
                "--root",
                str(self.root),
                "--context",
                "default",
                "--item",
                "M-5: waiting on Blaze",
            ],
            cwd=other,
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        captured = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(captured["context"]["items"][0]["id"], "M-5")
        self.assertTrue((self.store / "contexts" / "default.json").exists())
        self.assertFalse((self.root / ".stepper").exists())
        self.assertFalse((other / ".stepper").exists())

    def test_skill_directory_is_refused_and_its_repository_is_not(self):
        skill = STEPPER.resolve().parent
        code, data = self.cli("status", "--root", str(skill))
        self.assertEqual(code, 1)
        self.assertIn("skill directory", data["error"])
        self.assertIn("project root", data["error"])
        repo = STEPPER.resolve().parents[3]
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                "import importlib.util\n"
                "from pathlib import Path\n"
                f"spec = importlib.util.spec_from_file_location('stepper_under_test', {str(STEPPER)!r})\n"
                "mod = importlib.util.module_from_spec(spec)\n"
                "spec.loader.exec_module(mod)\n"
                f"mod.refuse_skill_checkout(Path({str(repo)!r}))\n",
            ],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def repo_with_subdir(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        sub = self.root / "pkg" / "inner"
        sub.mkdir(parents=True)
        return sub

    def test_hook_and_cli_agree_on_the_git_top_level(self):
        sub = self.repo_with_subdir()
        body = {"hook_event_name": "UserPromptSubmit", "session_id": "t1", "prompt": "stepper, track these",
                "workspace_roots": [str(sub)]}
        proc = subprocess.run([sys.executable, str(STEPPER), "hook", "--platform", "claude", "--tag", "stepper"],
                              input=json.dumps(body), text=True, capture_output=True, env=self.env, check=False)
        self.assertEqual(proc.returncode, 0)
        reported = json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertTrue(reported.rstrip(".").endswith("--root %s on every stepper command" % self.root.resolve()), reported)
        proc = subprocess.run([sys.executable, str(STEPPER), "status", "--session", "claude:t1"],
                              cwd=sub, text=True, capture_output=True, env=self.env, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["session"]["session_key"], "claude:t1")

    def test_hook_with_several_workspace_roots_uses_the_first(self):
        other = Path(tempfile.mkdtemp())
        body = {"hook_event_name": "UserPromptSubmit", "session_id": "t2", "prompt": "stepper, track these",
                "workspace_roots": [str(self.root), str(other)]}
        proc = subprocess.run([sys.executable, str(STEPPER), "hook", "--platform", "claude", "--tag", "stepper"],
                              input=json.dumps(body), text=True, capture_output=True, env=self.env, check=False)
        self.assertIn("--root %s on every" % self.root.resolve(), proc.stdout)
        self.assertNotIn(str(other.resolve()), proc.stdout)

    def test_hook_payload_missing_its_fields_is_silent_and_writes_nothing(self):
        for body in ({}, {"hook_event_name": "UserPromptSubmit"},
                     {"hook_event_name": "UserPromptSubmit", "prompt": "stepper, track these"}):
            with self.subTest(body=body):
                proc = subprocess.run([sys.executable, str(STEPPER), "hook", "--platform", "claude", "--tag", "stepper"],
                                      input=json.dumps(body), text=True, capture_output=True, env=self.env,
                                      cwd=self.root, check=False)
                self.assertEqual((proc.returncode, proc.stdout.strip()), (0, ""))
                self.assertFalse(self.store.exists())

    def test_hook_pointed_at_the_skill_directory_is_refused_like_the_cli(self):
        skill = STEPPER.resolve().parent
        body = {"hook_event_name": "UserPromptSubmit", "session_id": "t3", "prompt": "stepper, track these",
                "workspace_roots": [str(skill)]}
        proc = subprocess.run([sys.executable, str(STEPPER), "hook", "--platform", "claude", "--tag", "stepper"],
                              input=json.dumps(body), text=True, capture_output=True, env=self.env, check=False)
        self.assertEqual((proc.returncode, proc.stdout.strip()), (0, ""))
        self.assertFalse(self.store.exists())
        code, data = self.cli("status", "--root", str(skill))
        self.assertEqual(code, 1)

    def test_the_session_key_is_parsed_in_one_place(self):
        spec = __import__("importlib.util").util.spec_from_file_location("stepper_keys", STEPPER)
        mod = __import__("importlib.util").util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.split_session_key("claude:abc:def"), ("claude", "abc:def"))
        self.assertEqual(mod.join_session_key("cursor", "x"), "cursor:x")
        self.assertEqual(mod.session_key_from({"session_id": "s"}, "claude"), "claude:s")
        self.assertEqual(mod.session_key_from({"conversation_id": "c"}, "cursor"), "cursor:c")
        self.assertIsNone(mod.session_key_from({}, "claude"))

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
        before = json.loads((self.store / "contexts" / "default.json").read_text())
        code, _data = self.cli("detach", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        after = json.loads((self.store / "contexts" / "default.json").read_text())
        self.assertEqual(after["items"], before["items"])
        self.assertIsNone(after["lease"])
        self.cli("attach", "--session", "cursor:aaa", "default")
        code, _data, _out = self.hook(
            "cursor",
            {"hook_event_name": "sessionEnd", "conversation_id": "aaa"},
        )
        self.assertEqual(code, 0)
        ended = json.loads((self.store / "contexts" / "default.json").read_text())
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
        self.cli("free", "--session", "cursor:aaa", "AC-4")
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
        self.assertEqual(code, 0, data)
        self.assertEqual(data["context"]["lease"]["session_key"], "cursor:aaa")
        code, again = self.cli(
            "capture", "--session", "cursor:aaa", "--context", "default", "--item", "AC-9: another"
        )
        self.assertEqual(code, 1)
        self.assertIn("is open", again["error"])
        self.assertTrue((self.store / "contexts" / "default.json").exists())
        self.assertTrue((self.store / "contexts" / "other.json").exists())

    def test_session_holds_several_contexts(self):
        self.capture()
        code, _second = self.cli(
            "capture",
            "--session",
            "cursor:aaa",
            "--context",
            "other",
            "--item",
            "M-5: waiting on Blaze",
        )
        self.assertEqual(code, 0)
        code, status = self.cli("status", "--session", "cursor:aaa")
        briefs = {row["id"]: row["brief"] for row in status["held"]}
        self.assertEqual(set(briefs), {"default", "other"})
        self.assertEqual(briefs["default"]["position"], "1 of 2")
        self.assertEqual(briefs["default"]["done"], [])
        self.assertEqual(briefs["other"]["left"], ["M-5"])
        self.cli("pause", "--session", "cursor:aaa", "--context", "default")
        self.register("cursor:aaa", prompt="fix AC-3", generation="g-held")
        code, reminded, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g-held",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertIn("M-5", reminded["followup_message"])
        self.assertNotIn("AC-3 active", reminded["followup_message"])
        self.cli("detach", "--session", "cursor:aaa", "--context", "other")
        code, status = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual([row["id"] for row in status["held"]], ["default"])
        self.cli(
            "capture",
            "--session",
            "cursor:aaa",
            "--context",
            "third",
            "--item",
            "M-6: another",
        )
        self.hook(
            "cursor",
            {"hook_event_name": "sessionEnd", "conversation_id": "aaa"},
        )
        for name in ("default", "third"):
            stored = json.loads((self.store / "contexts" / f"{name}.json").read_text())
            self.assertIsNone(stored["lease"])
            self.assertTrue(stored["items"])
        self.cli(
            "capture",
            "--session",
            "cursor:aaa",
            "--context",
            "fresh",
            "--item",
            "M-8: fresh",
        )
        self.cli(
            "capture",
            "--session",
            "cursor:aaa",
            "--context",
            "kept",
            "--item",
            "M-7: stays",
        )
        self.register("cursor:bbb")
        code, denied = self.cli("attach", "--session", "cursor:bbb", "fresh")
        self.assertEqual(code, 1)
        self.assertIn("--take", denied["error"])
        code, taken = self.cli("attach", "--session", "cursor:bbb", "fresh", "--take")
        self.assertEqual(code, 0)
        self.assertEqual(taken["context"]["lease"]["session_key"], "cursor:bbb")
        code, status = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual([row["id"] for row in status["held"]], ["kept"])

    def test_capture_after_close_archives_the_closed_context(self):
        self.capture()
        self.cli("close", "--session", "cursor:aaa")
        code, data = self.capture()
        self.assertEqual(code, 0, data)
        self.assertFalse(data["context"]["closed"])
        self.assertEqual(data["context"]["lease"]["session_key"], "cursor:aaa")
        archived = self.archived_contexts("default")
        self.assertEqual(len(archived), 1)
        self.assertTrue(archived[0]["closed"])

    def test_capture_over_open_context_says_it_is_open(self):
        self.capture()
        self.cli("detach", "--session", "cursor:aaa")
        code, data = self.cli(
            "capture", "--session", "cursor:aaa", "--context", "default", "--item", "AC-9: x"
        )
        self.assertEqual(code, 1)
        self.assertIn("is open", data["error"])

    def test_capture_requires_a_name(self):
        self.register()
        proc = subprocess.run(
            [
                sys.executable,
                str(STEPPER),
                "capture",
                "--session",
                "cursor:aaa",
                "--root",
                str(self.root),
                "--item",
                "AC-9: x",
            ],
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((self.store / "contexts").exists() and any((self.store / "contexts").glob("*.json")))

    def test_state_change_names_the_context_it_changes(self):
        self.capture()
        code, data = self.cli(
            "verify",
            "--session",
            "cursor:aaa",
            "--context",
            "other",
            "AC-3",
            "--evidence",
            "sent",
        )
        self.assertEqual(code, 1)
        self.assertIn("holds default, not other", data["error"])
        stored = json.loads((self.store / "contexts" / "default.json").read_text())
        self.assertEqual(stored["items"][0]["status"], "active")

    def test_repo_label_is_the_origin_of_the_checkout(self):
        remote = "https://github.com/example/widget.git"
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(self.root), "remote", "add", "origin", remote],
            check=True,
            capture_output=True,
        )
        code, data = self.capture()
        self.assertEqual(code, 0)
        self.assertEqual(data["context"]["repo"], remote)
        code, status = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(status["context"]["repo"], remote)
        self.assertEqual(status["brief"]["position"], "1 of 2")

    def test_checkout_with_no_origin_leaves_the_repo_label_empty(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        code, data = self.capture()
        self.assertEqual(code, 0)
        self.assertIsNone(data["context"]["repo"])

    def test_omitted_checkout_leaves_the_repo_label_empty(self):
        remote = "https://github.com/example/widget.git"
        checkout = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init"], cwd=checkout, check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(checkout), "remote", "add", "origin", remote],
            check=True,
            capture_output=True,
        )
        self.register()
        proc = subprocess.run(
            [
                sys.executable,
                str(STEPPER),
                "capture",
                "--session",
                "cursor:aaa",
                "--context",
                "default",
                "--item",
                "AC-3: reset email is sent",
            ],
            cwd=checkout,
            text=True,
            capture_output=True,
            env=self.env,
            check=False,
        )
        data = json.loads(proc.stdout)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIsNone(data["context"]["repo"])

    def test_two_names_can_carry_the_same_items(self):
        self.capture()
        self.register("cursor:bbb")
        code, data = self.cli(
            "capture",
            "--session",
            "cursor:bbb",
            "--context",
            "other",
            "--item",
            "AC-3: reset email is sent",
            "--item",
            "AC-4: rate limit returns 429",
        )
        self.assertEqual(code, 0, data)
        code, inventory = self.cli("status")
        by_id = {ctx["id"]: ctx for ctx in inventory["contexts"]}
        self.assertEqual(set(by_id), {"default", "other"})
        code, held = self.cli("status", "--session", "cursor:aaa")
        code, also = self.cli("status", "--session", "cursor:bbb")
        self.assertEqual(
            [item["description"] for item in held["context"]["items"]],
            [item["description"] for item in also["context"]["items"]],
        )

    def test_open_context_error_names_the_holder(self):
        self.capture()
        self.register("cursor:bbb")
        code, data = self.cli(
            "capture", "--session", "cursor:bbb", "--context", "default", "--item", "AC-9: x"
        )
        self.assertEqual(code, 1)
        self.assertIn("held by cursor:aaa", data["error"])
        self.assertIn("--take", data["error"])

    def test_open_context_error_says_when_nobody_holds_it(self):
        self.capture()
        self.cli("detach", "--session", "cursor:aaa")
        code, data = self.cli(
            "capture", "--session", "cursor:aaa", "--context", "default", "--item", "AC-9: x"
        )
        self.assertEqual(code, 1)
        self.assertIn("no session holds it", data["error"])

    def test_corrupt_file_is_preserved_and_not_replaced(self):
        self.capture()
        path = self.store / "contexts" / "default.json"
        original = b"{not json"
        path.write_bytes(original)
        code, data = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "sent")
        self.assertEqual(code, 1)
        self.assertIn("left in place", data["error"])
        self.assertEqual(path.read_bytes(), original)
        contexts = list((self.store / "contexts").glob("*.json"))
        self.assertEqual(contexts, [path])
        copies = list((self.store / "quarantine").glob("*"))
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), original)
        code, status = self.cli("status")
        self.assertEqual(code, 0)
        self.assertTrue(any(Path(item).name == "default.json" for item in status["corrupt_files"]))
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list((self.store / "contexts").glob("*.json")), [path])

    def test_failed_hook_does_not_change_context_bytes(self):
        self.capture()
        path = self.store / "contexts" / "default.json"
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
        self.assertFalse((self.store / "suggestions.json").exists())
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

    def test_claude_tracking_prompt_registers_session_and_resume_repeats_key(self):
        sessions = self.store / "sessions"
        code, _data, out = self.hook(
            "claude",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "5155e88d-741e-4fcb-9fbb-5e86a3830714",
                "cwd": str(self.root),
                "prompt": "What is the weather?",
            },
            workspace=False,
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(list(sessions.glob("*.json")), [])
        code, submitted, _out = self.hook(
            "claude",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "5155e88d-741e-4fcb-9fbb-5e86a3830714",
                "cwd": str(self.root),
                "prompt": "Track these with stepper",
            },
            workspace=False,
        )
        text = submitted["hookSpecificOutput"]["additionalContext"]
        key = "claude:5155e88d-741e-4fcb-9fbb-5e86a3830714"
        root = str(self.root.resolve())
        self.assertEqual(
            text,
            f"Stepper session: {key}. Project root: {root}. "
            f"Pass --session {key} --root {root} on every stepper command.",
        )
        self.assertEqual(len(list(sessions.glob("*.json"))), 1)
        self.assertEqual(list((self.store / "contexts").glob("*.json")), [])
        code, _data, out = self.hook(
            "claude",
            {
                "hook_event_name": "SessionEnd",
                "session_id": "5155e88d-741e-4fcb-9fbb-5e86a3830714",
                "cwd": str(self.root),
            },
            workspace=False,
        )
        self.assertEqual(out, "")
        code, resumed, _out = self.hook(
            "claude",
            {
                "hook_event_name": "SessionStart",
                "source": "resume",
                "session_id": "5155e88d-741e-4fcb-9fbb-5e86a3830714",
                "cwd": str(self.root),
            },
            workspace=False,
        )
        self.assertEqual(resumed["hookSpecificOutput"]["additionalContext"], text)
        code, _data, out = self.hook(
            "claude",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "5155e88d-741e-4fcb-9fbb-5e86a3830714",
                "cwd": str(self.root),
                "prompt": "What is the weather?",
            },
            workspace=False,
        )
        self.assertEqual(out, "")

    def test_claude_stop_offers_once_without_a_prior_session(self):
        sessions = self.store / "sessions"
        contexts = self.store / "contexts"
        code, _data, out = self.hook(
            "claude",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "fresh",
                "prompt": "Evaluate the acceptance criteria and report which ones still fail.",
            },
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(list(sessions.glob("*.json")), [])
        self.assertEqual(list(contexts.glob("*.json")), [])
        stop = {
            "hook_event_name": "Stop",
            "session_id": "fresh",
            "prompt_id": "p1",
            "stop_hook_active": False,
            "last_assistant_message": AC_REPORT,
        }
        code, first, _out = self.hook("claude", stop)
        self.assertEqual(code, 0)
        text = first["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(text.count("Stepper candidate"), 1)
        self.assertIn("2 items", text)
        self.assertIn("AC-3", text)
        self.assertIn("AC-4", text)
        self.assertNotIn("AC-1", text)
        self.assertEqual(len(list(sessions.glob("*.json"))), 1)
        self.assertEqual(list(contexts.glob("*.json")), [])
        code, _data, out = self.hook("claude", stop)
        self.assertEqual(out, "")
        repeated = dict(stop, prompt_id="p2")
        code, _data, out = self.hook("claude", repeated)
        self.assertEqual(out, "")

    def test_pr_queue_prompt_registers_a_session_and_announces_the_key(self):
        sessions = self.store / "sessions"
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "beforeSubmitPrompt",
                "conversation_id": "aaa",
                "generation_id": "turn",
                "prompt": "/pr-queue",
            },
        )
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertEqual(len(list(sessions.glob("*.json"))), 1)
        code, announced, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "postToolUse",
                "conversation_id": "aaa",
                "generation_id": "turn",
                "tool_name": "get_me",
            },
        )
        self.assertEqual(code, 0)
        root = str(self.root.resolve())
        self.assertEqual(
            announced["additional_context"],
            f"Stepper session: cursor:aaa. Project root: {root}. "
            f"Pass --session cursor:aaa --root {root} on every stepper command.",
        )
        code, submitted, _out = self.hook(
            "claude",
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "5155e88d-741e-4fcb-9fbb-5e86a3830714",
                "cwd": str(self.root),
                "prompt": "/pr-queue backlog",
            },
            workspace=False,
        )
        self.assertIn("Stepper session: claude:5155e88d-741e-4fcb-9fbb-5e86a3830714.", submitted["hookSpecificOutput"]["additionalContext"])

    def test_cursor_offer_follows_the_observed_response_then_stop_order(self):
        sessions = self.store / "sessions"
        contexts = self.store / "contexts"
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "beforeSubmitPrompt",
                "conversation_id": "aaa",
                "generation_id": "turn",
                "prompt": "Evaluate the acceptance criteria and report which ones still fail.",
            },
        )
        self.assertEqual(out, "")
        self.assertEqual(list(sessions.glob("*.json")), [])
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "postToolUse",
                "conversation_id": "aaa",
                "generation_id": "turn",
                "tool_name": "Shell",
            },
        )
        self.assertEqual(out, "")
        self.assertEqual(list(sessions.glob("*.json")), [])
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "afterAgentResponse",
                "conversation_id": "aaa",
                "generation_id": "turn",
                "text": AC_REPORT,
            },
        )
        self.assertEqual(out, "")
        self.assertEqual(len(list(sessions.glob("*.json"))), 1)
        stop = {
            "hook_event_name": "stop",
            "conversation_id": "aaa",
            "generation_id": "followup",
            "status": "completed",
            "loop_count": 0,
        }
        code, first, _out = self.hook("cursor", stop)
        self.assertEqual(first["followup_message"].count("Stepper candidate"), 1)
        self.assertIn("AC-3", first["followup_message"])
        self.assertIn("AC-4", first["followup_message"])
        self.assertEqual(list(contexts.glob("*.json")), [])
        code, _data, out = self.hook("cursor", stop)
        self.assertEqual(out, "")
        code, _data, out = self.hook("cursor", dict(stop, generation_id="followup-2"))
        self.assertEqual(out, "")

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

    def test_teaching_owner_suppresses_stop_and_session_start_reminders(self):
        self.capture()
        latch = self.root / ".claude" / "turn-owner.json"
        latch.parent.mkdir()
        latch.write_text(
            json.dumps(
                {
                    "session_key": "cursor:aaa",
                    "owner": "understand",
                    "pending_offer": False,
                }
            )
        )
        self.register("cursor:aaa", prompt="fix AC-3", generation="g-teach")
        code, _data, out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g-teach",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertEqual(out, "")
        code, _data, out = self.hook(
            "cursor",
            {"hook_event_name": "sessionStart", "conversation_id": "aaa", "generation_id": "g-teach-2"},
        )
        self.assertEqual(out, "")
        latch.write_text(
            json.dumps(
                {
                    "session_key": "cursor:other",
                    "owner": "pair",
                    "pending_offer": False,
                }
            )
        )
        self.register("cursor:aaa", prompt="fix AC-3", generation="g-back")
        code, data, _out = self.hook(
            "cursor",
            {
                "hook_event_name": "stop",
                "conversation_id": "aaa",
                "generation_id": "g-back",
                "status": "completed",
                "loop_count": 0,
            },
        )
        self.assertIn("AC-3 active", data["followup_message"])

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

    def test_checkout_gains_no_store(self):
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        self.capture()
        self.assertFalse((self.root / ".stepper").exists())
        self.assertTrue((self.store / "contexts" / "default.json").exists())

    def item(self, data, item_id):
        return next(item for item in data["context"]["items"] if item["id"] == item_id)

    def test_legacy_flat_context_has_no_parent_and_keeps_its_reminder(self):
        self.capture()
        path = self.store / "contexts" / "default.json"
        stored = json.loads(path.read_text())
        for item in stored["items"]:
            item.pop("parent_id", None)
        path.write_text(json.dumps(stored, indent=2) + "\n")
        before = path.read_bytes()
        code, data = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(data["progress"]["top_level"], {"resolved": 0, "total": 2})
        self.assertEqual(data["progress"]["active_path"], ["AC-3"])
        self.assertIn("AC-3 active", data["reminder"])
        self.assertNotIn("top-level", data["reminder"])
        code, verified = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "sent")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(verified, "AC-4")["status"], "active")
        self.assertIsNone(self.item(verified, "AC-4")["parent_id"])

    def test_substeps_keep_ids_and_do_not_move_focus(self):
        self.capture()
        code, added = self.cli(
            "add",
            "--session",
            "cursor:aaa",
            "--parent",
            "AC-3",
            "--item",
            "AC-3b: check the reset token",
            "--item",
            "AC-3a: check the template",
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.item(added, "AC-3")["status"], "active")
        self.assertEqual(self.item(added, "AC-3a")["parent_id"], "AC-3")
        self.assertEqual(self.item(added, "AC-3b")["parent_id"], "AC-3")
        code, nested = self.cli(
            "add",
            "--session",
            "cursor:aaa",
            "--parent",
            "AC-3b",
            "--item",
            "AC-3b-1: check the token expiry",
            "--item",
            "look at the logs",
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.item(nested, "AC-3b-1")["parent_id"], "AC-3b")
        generated = next(item for item in nested["context"]["items"] if item["id"].startswith("item-"))
        self.assertEqual(generated["parent_id"], "AC-3b")
        self.assertEqual(nested["progress"]["active_path"], ["AC-3"])
        self.assertEqual(nested["progress"]["top_level"], {"resolved": 0, "total": 2})
        code, tree = self.cli("status", "--session", "cursor:aaa", "--tree")
        self.assertEqual(code, 0)
        ac3 = next(node for node in tree["tree"] if node["id"] == "AC-3")
        self.assertEqual(ac3["children_total"], 2)
        self.assertEqual([child["id"] for child in ac3["children"]], ["AC-3b", "AC-3a"])
        code, limited = self.cli(
            "add",
            "--session",
            "cursor:aaa",
            "--parent",
            "AC-3b-1",
            "--item",
            "AC-3b-1-a: too deep",
        )
        self.assertEqual(code, 1)
        self.assertIn("exceeds MAX_DEPTH 2", limited["error"])
        code, duplicate = self.cli(
            "add",
            "--session",
            "cursor:aaa",
            "--parent",
            "AC-3",
            "--item",
            "AC-3a: again",
        )
        self.assertEqual(code, 1)
        self.assertIn("already exists", duplicate["error"])

    def test_focus_reactivates_a_deferred_ancestor(self):
        self.capture()
        self.cli("add", "--session", "cursor:aaa", "--parent", "AC-3", "--item", "AC-3a: template")
        self.cli("defer", "--session", "cursor:aaa", "AC-3a")
        self.cli("defer", "--session", "cursor:aaa", "AC-3")
        code, focused = self.cli("focus", "--session", "cursor:aaa", "AC-3a")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(focused, "AC-3")["status"], "pending")
        self.assertEqual(self.item(focused, "AC-3a")["status"], "active")
        self.assertEqual(focused["progress"]["active_path"], ["AC-3", "AC-3a"])

    def test_next_item_enters_a_pending_sibling_branch(self):
        self.capture()
        self.cli(
            "add",
            "--session",
            "cursor:aaa",
            "--parent",
            "AC-3",
            "--item",
            "AC-3a: template",
            "--item",
            "AC-3b: token",
        )
        self.cli("add", "--session", "cursor:aaa", "--parent", "AC-3b", "--item", "AC-3b-1: expiry")
        self.cli("focus", "--session", "cursor:aaa", "AC-3a")
        code, stepped = self.cli("verify", "--session", "cursor:aaa", "AC-3a", "--evidence", "template ok")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(stepped, "AC-3b-1")["status"], "active")
        self.assertEqual(self.item(stepped, "AC-4")["status"], "pending")
        self.assertIn("AC-3 → AC-3b → AC-3b-1 active", stepped["reminder"])
        code, parent = self.cli("verify", "--session", "cursor:aaa", "AC-3b-1", "--evidence", "expiry ok")
        self.assertEqual(self.item(parent, "AC-3b")["status"], "active")
        self.assertNotEqual(self.item(parent, "AC-3b")["status"], "verified")
        code, mid = self.cli("verify", "--session", "cursor:aaa", "AC-3b", "--evidence", "token ok")
        self.assertEqual(self.item(mid, "AC-3")["status"], "active")
        code, done = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "reset ok")
        self.assertEqual(self.item(done, "AC-3")["status"], "verified")
        self.assertEqual(self.item(done, "AC-4")["status"], "active")
        self.assertEqual(done["progress"]["top_level"], {"resolved": 1, "total": 2})

    def test_parent_verification_cancel_and_reopen(self):
        self.capture()
        self.cli("add", "--session", "cursor:aaa", "--parent", "AC-3", "--item", "AC-3a: template")
        self.cli("add", "--session", "cursor:aaa", "--parent", "AC-3", "--item", "AC-3b: token")
        code, blocked = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "too soon")
        self.assertEqual(code, 1)
        self.assertIn("cannot verify AC-3 until", blocked["error"])
        code, cancelled = self.cli("cancel", "--session", "cursor:aaa", "AC-3")
        self.assertEqual(code, 1)
        self.assertIn("cannot cancel AC-3 until", cancelled["error"])
        self.cli("defer", "--session", "cursor:aaa", "AC-3a")
        code, deferred = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "too soon")
        self.assertEqual(code, 1)
        self.assertIn("AC-3a", deferred["error"])
        self.cli("focus", "--session", "cursor:aaa", "AC-3a")
        code, reopened = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(self.item(reopened, "AC-3a")["status"], "active")
        self.assertEqual(self.item(reopened, "AC-3")["status"], "pending")
        self.cli("verify", "--session", "cursor:aaa", "AC-3a", "--evidence", "template ok")
        self.cli("verify", "--session", "cursor:aaa", "AC-3b", "--evidence", "token ok")
        code, ready = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "reset ok")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(ready, "AC-3")["status"], "verified")
        code, child = self.cli(
            "add", "--session", "cursor:aaa", "--parent", "AC-3", "--item", "AC-3c: later"
        )
        self.assertEqual(code, 1)
        self.assertIn("because it is verified", child["error"])

    def test_walk_follows_a_branch_deeper_than_the_add_limit(self):
        self.capture()
        path = self.store / "contexts" / "default.json"
        stored = json.loads(path.read_text())
        stored["items"][0]["status"] = "pending"
        stored["items"][1]["status"] = "pending"
        deep = [
            ("AC-3a", "AC-3", "pending", 0),
            ("AC-3a-1", "AC-3a", "active", 0),
            ("AC-3a-9", "AC-3a", "pending", 1),
            ("AC-3a-9-1", "AC-3a-9", "blocked", 0),
            ("AC-3a-8", "AC-3a", "deferred", 2),
            ("AC-3a-8-1", "AC-3a-8", "pending", 0),
            ("AC-3a-2", "AC-3a", "pending", 3),
            ("AC-3a-2-1", "AC-3a-2", "pending", 0),
        ]
        for item_id, parent_id, status, order in deep:
            stored["items"].append(
                {
                    "id": item_id,
                    "description": item_id,
                    "completion_criteria": item_id,
                    "status": status,
                    "evidence": None,
                    "blocked_reason": "waiting" if status == "blocked" else None,
                    "order": order,
                    "parent_id": parent_id,
                }
            )
        path.write_text(json.dumps(stored, indent=2) + "\n")
        code, stepped = self.cli("verify", "--session", "cursor:aaa", "AC-3a-1", "--evidence", "deep ok")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(stepped, "AC-3a-2-1")["status"], "active")
        self.assertEqual(self.item(stepped, "AC-3a-9")["status"], "pending")
        self.assertEqual(self.item(stepped, "AC-3a-8-1")["status"], "pending")
        self.assertEqual(self.item(stepped, "AC-4")["status"], "pending")

    def test_selection_skips_a_parent_with_blocked_or_deferred_children(self):
        self.capture()
        self.cli("free", "--session", "cursor:aaa", "AC-4")
        self.cli("focus", "--session", "cursor:aaa", "AC-4")
        self.cli("focus", "--session", "cursor:aaa", "AC-3")
        code, added = self.cli(
            "add",
            "--session",
            "cursor:aaa",
            "--parent",
            "AC-3",
            "--item",
            "AC-3a: blocked child",
            "--item",
            "AC-3b: deferred child",
            "--item",
            "AC-3c: verified child",
            "--item",
            "AC-3d: cancelled child",
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.item(added, "AC-3")["status"], "active")
        self.cli("focus", "--session", "cursor:aaa", "AC-3a")
        self.cli("block", "--session", "cursor:aaa", "AC-3a", "--reason", "waiting")
        self.cli("defer", "--session", "cursor:aaa", "AC-3b")
        self.cli("focus", "--session", "cursor:aaa", "AC-3c")
        self.cli("verify", "--session", "cursor:aaa", "AC-3c", "--evidence", "done")
        self.cli("cancel", "--session", "cursor:aaa", "AC-3d")
        self.cli("add", "--session", "cursor:aaa", "--item", "AC-5: later leaf")
        self.cli("free", "--session", "cursor:aaa", "AC-4")
        self.cli("focus", "--session", "cursor:aaa", "AC-4")
        code, skipped = self.cli("verify", "--session", "cursor:aaa", "AC-4", "--evidence", "sent")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(skipped, "AC-5")["status"], "active")
        self.assertEqual(self.item(skipped, "AC-3")["status"], "pending")
        self.cli("unblock", "--session", "cursor:aaa", "AC-3a")
        code, descended = self.cli("verify", "--session", "cursor:aaa", "AC-5", "--evidence", "sent")
        self.assertEqual(self.item(descended, "AC-3a")["status"], "active")
        self.assertEqual(self.item(descended, "AC-3")["status"], "pending")
        self.cli("cancel", "--session", "cursor:aaa", "AC-3b")
        code, eligible = self.cli("verify", "--session", "cursor:aaa", "AC-3a", "--evidence", "unblocked")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(eligible, "AC-3")["status"], "active")
        self.assertNotEqual(self.item(eligible, "AC-3")["status"], "verified")

    def test_selection_leaves_no_active_item_when_nothing_actionable_remains(self):
        self.capture()
        self.cli("add", "--session", "cursor:aaa", "--parent", "AC-4", "--item", "AC-4a: blocked")
        self.cli("add", "--session", "cursor:aaa", "--parent", "AC-4", "--item", "AC-4b: deferred")
        self.cli("focus", "--session", "cursor:aaa", "AC-4a")
        self.cli("block", "--session", "cursor:aaa", "AC-4a", "--reason", "waiting")
        self.cli("defer", "--session", "cursor:aaa", "AC-4b")
        code, done = self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "sent")
        self.assertEqual(code, 0)
        self.assertTrue(all(item["status"] != "active" for item in done["context"]["items"]))
        self.assertEqual(self.item(done, "AC-4")["status"], "pending")
        self.assertEqual(done["progress"]["active_path"], [])

    def test_capture_depends_on_the_previous_item_and_status_briefs(self):
        code, data = self.capture()
        self.assertEqual(code, 0)
        self.assertEqual(self.item(data, "AC-3")["depends_on"], [])
        self.assertEqual(self.item(data, "AC-4")["depends_on"], ["AC-3"])
        brief = data["brief"]
        self.assertEqual(brief["done"], [])
        self.assertEqual(brief["blocked"], [])
        self.assertEqual(brief["left"], ["AC-3", "AC-4"])
        self.assertEqual(brief["position"], "1 of 2")

    def test_status_puts_each_item_on_its_own_row(self):
        self.capture()
        code, data = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertEqual(
            data["table"],
            "\n".join(
                [
                    "1 of 2",
                    "",
                    "| Item | Status | Description |",
                    "| --- | --- | --- |",
                    "| AC-3 | active | reset email is sent |",
                    "| AC-4 | pending | rate limit returns 429 |",
                ]
            ),
        )

    def test_status_table_notes_evidence_and_a_block_reason(self):
        self.capture()
        self.cli("verify", "--session", "cursor:aaa", "AC-3", "--evidence", "sent | ok")
        self.cli("block", "--session", "cursor:aaa", "AC-4", "--reason", "waiting\non Blaze")
        code, data = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertIn("| AC-3 | verified | reset email is sent | sent \\| ok |", data["table"])
        self.assertIn("| AC-4 | blocked | rate limit returns 429 | waiting on Blaze |", data["table"])
        self.assertTrue(data["table"].startswith("2 of 2\n"))

    def test_status_table_names_the_parent_of_a_child(self):
        self.capture()
        code, added = self.cli(
            "add",
            "--session",
            "cursor:aaa",
            "--parent",
            "AC-3",
            "--item",
            "AC-3a: send the message",
        )
        self.assertEqual(code, 0, added)
        code, data = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertEqual(
            data["table"],
            "\n".join(
                [
                    "1 of 2",
                    "",
                    "| Item | Parent | Status | Description |",
                    "| --- | --- | --- | --- |",
                    "| AC-3 |  | active | reset email is sent |",
                    "| AC-3a | AC-3 | pending | send the message |",
                    "| AC-4 |  | pending | rate limit returns 429 |",
                ]
            ),
        )

    def test_status_table_is_empty_when_no_list_is_held(self):
        code, data = self.cli("status", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertIsNone(data["context"])
        self.assertEqual(data["table"], "")

    def test_skip_refuses_while_the_next_item_depends_on_the_held_item(self):
        self.capture()
        code, blocked = self.cli("block", "--session", "cursor:aaa", "AC-3", "--reason", "waiting on Blaze")
        self.assertEqual(code, 0)
        self.assertIn("Hold", blocked["reminder"])
        code, denied = self.cli("skip", "--session", "cursor:aaa")
        self.assertEqual(code, 1)
        self.assertIn("AC-4 depends on AC-3", denied["error"])
        self.assertIn("hold", denied["error"])
        code, freed = self.cli("free", "--session", "cursor:aaa", "AC-4")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(freed, "AC-4")["depends_on"], [])
        code, skipped = self.cli("skip", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(skipped, "AC-4")["status"], "active")
        self.assertEqual(self.item(skipped, "AC-3")["status"], "blocked")

    def test_add_after_a_block_leaves_the_dependent_successor_pending(self):
        self.capture()
        self.cli("block", "--session", "cursor:aaa", "AC-3", "--reason", "waiting on Blaze")
        code, added = self.cli("add", "--session", "cursor:aaa", "--item", "AC-5: audit log")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(added, "AC-4")["status"], "pending")
        self.assertEqual(self.item(added, "AC-5")["status"], "pending")
        self.assertEqual(self.item(added, "AC-3")["status"], "blocked")
        self.assertFalse([i for i in added["context"]["items"] if i["status"] == "active"])

    def test_add_agrees_with_skip_about_the_dependent_successor(self):
        self.capture()
        self.cli("block", "--session", "cursor:aaa", "AC-3", "--reason", "waiting on Blaze")
        code, denied = self.cli("skip", "--session", "cursor:aaa")
        self.assertEqual(code, 1)
        code, added = self.cli("add", "--session", "cursor:aaa", "--item", "AC-5: audit log")
        self.assertNotEqual(self.item(added, "AC-4")["status"], "active")

    def test_add_while_an_item_is_active_leaves_focus_where_it_was(self):
        self.capture()
        code, added = self.cli("add", "--session", "cursor:aaa", "--item", "AC-5: audit log")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(added, "AC-3")["status"], "active")
        self.assertEqual([i["id"] for i in added["context"]["items"] if i["status"] == "active"], ["AC-3"])

    def test_order_marks_an_item_free_so_skip_can_pass_the_held_item(self):
        self.capture()
        self.cli("block", "--session", "cursor:aaa", "AC-3", "--reason", "waiting on Blaze")
        code, ordered = self.cli(
            "order",
            "--session",
            "cursor:aaa",
            "--item",
            "AC-3",
            "--item",
            "AC-4",
            "--free",
            "AC-4",
        )
        self.assertEqual(code, 0)
        self.assertEqual(self.item(ordered, "AC-4")["depends_on"], [])
        code, skipped = self.cli("skip", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertEqual(self.item(skipped, "AC-4")["status"], "active")
        self.assertEqual(self.item(skipped, "AC-3")["status"], "blocked")

    def test_drop_archives_without_verifying_and_the_same_session_can_capture(self):
        self.capture()
        session = self.store / "sessions"
        before = list(session.glob("*.json"))
        code, dropped = self.cli("drop", "--session", "cursor:aaa")
        self.assertEqual(code, 0)
        self.assertIsNone(dropped["context"])
        self.assertEqual(dropped["brief"], {"done": [], "left": [], "blocked": [], "position": "none"})
        self.assertEqual(list((self.store / "contexts").glob("*.json")), [])
        archived = self.archived_contexts("default")
        self.assertEqual(len(archived), 1)
        stored = archived[0]
        self.assertTrue(stored["closed"])
        self.assertIsNone(stored["lease"])
        self.assertTrue(all(item["status"] != "verified" for item in stored["items"]))
        self.assertEqual(list(session.glob("*.json")), before)
        code, again = self.capture()
        self.assertEqual(code, 0)
        self.assertEqual(again["context"]["items"][0]["status"], "active")

    def test_replace_cancels_outstanding_items_without_verifying_them(self):
        self.capture()
        code, replaced = self.cli(
            "replace",
            "--session",
            "cursor:aaa",
            "--item",
            "M-5: waiting on Blaze",
        )
        self.assertEqual(code, 0, replaced)
        self.assertEqual(self.item(replaced, "M-5")["status"], "active")
        self.assertEqual(self.item(replaced, "AC-3")["status"], "cancelled")
        self.assertIsNone(self.item(replaced, "AC-3")["evidence"])
        self.assertEqual(self.item(replaced, "AC-4")["status"], "cancelled")
        self.assertIsNone(self.item(replaced, "AC-4")["evidence"])
        self.assertEqual(replaced["brief"]["left"], ["M-5"])
        self.assertEqual(replaced["brief"]["done"], [])
        self.assertEqual(replaced["brief"]["blocked"], [])

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
