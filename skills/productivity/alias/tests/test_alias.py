#!/usr/bin/env python3
"""CLI tests for the alias cache. No Claude or Cursor process is involved."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ALIAS = Path(__file__).resolve().parents[1] / "alias.py"

CONFIG = """
cache: {cache}
tools:
  - tool: mcp__acme__find_employee
    query: name
    type: person
    id: employee
    extract: 'Employee ID: (E[0-9]+)'
"""


class AliasTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.home = self.root / "home"
        self.home.mkdir()
        self.cache = self.root / "aliases.yaml"
        self.config = self.root / "config.yaml"
        self.config.write_text(CONFIG.format(cache=self.cache))
        self.env = {**os.environ, "ALIAS_HOME": str(self.home), "ALIAS_CONFIG": str(self.config)}

    def run_cli(self, *args, stdin=None):
        proc = subprocess.run(
            [sys.executable, str(ALIAS), *args],
            text=True,
            input=stdin,
            capture_output=True,
            env=self.env,
            check=False,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, data

    def hook(self, platform, payload):
        return self.run_cli("hook", "--platform", platform, "--tag", "alias", stdin=json.dumps(payload))

    def test_add_and_get_roundtrip_ids_and_pronouns(self):
        code, added = self.run_cli(
            "add", "person", "Ada Lovelace", "pronouns=she/her", "ids.employee=E1", "email=ada@acme.test"
        )
        self.assertEqual(code, 0)
        self.assertEqual(added["added"], "ada_lovelace")
        code, got = self.run_cli("get", "ada")
        self.assertEqual(got["match"], "ada_lovelace")
        self.assertEqual(got["pronouns"], "she/her")
        self.assertEqual(got["ids"]["employee"], "E1")
        self.assertNotIn("_stub", got)

    def test_add_refuses_an_existing_name(self):
        self.run_cli("add", "person", "Ada Lovelace", "ids.employee=E1")
        code, data = self.run_cli("add", "person", "Ada", "ids.employee=E2")
        self.assertEqual(code, 1)
        self.assertIn("already cached", data["error"])

    def test_longer_alias_wins(self):
        self.cache.write_text(
            "\n".join(
                [
                    "ada:",
                    "  aliases: [Ada]",
                    "  type: person",
                    "  ids:",
                    "    employee: E1",
                    "ada_lovelace:",
                    "  aliases: [Ada Lovelace]",
                    "  type: person",
                    "  ids:",
                    "    employee: E2",
                    "",
                ]
            )
        )
        _, got = self.run_cli("get", "Ada Lovelace")
        self.assertEqual(got["ids"]["employee"], "E2")

    def test_post_creates_on_one_match_and_pre_skips_the_next_call(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__acme__find_employee",
            "tool_input": {"name": "Grace Hopper"},
            "tool_response": "Name: Grace Hopper\nEmployee ID: E9\n",
        }
        code, data = self.hook("claude", payload)
        self.assertEqual(code, 0)
        self.assertIn("ids.employee=E9", data["hookSpecificOutput"]["additionalContext"])
        _, got = self.run_cli("get", "Grace Hopper")
        self.assertEqual(got["ids"]["employee"], "E9")
        self.assertNotIn("_stub", got)

        pre = {
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__acme__find_employee",
            "tool_input": {"name": "Grace"},
        }
        _, decision = self.hook("claude", pre)
        self.assertEqual(decision["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertIn("E9", decision["hookSpecificOutput"]["permissionDecisionReason"])

    def test_post_stubs_when_several_ids_match(self):
        payload = {
            "hook_event_name": "PostToolUse",
            "tool_name": "mcp__acme__find_employee",
            "tool_input": {"name": "Pat"},
            "tool_response": "Employee ID: E1\nEmployee ID: E2\n",
        }
        self.hook("claude", payload)
        _, got = self.run_cli("get", "Pat")
        self.assertEqual(got["match"], "pat")
        self.assertNotIn("ids", got)

    def test_post_fills_an_empty_id_and_promotes_a_stub(self):
        self.hook(
            "claude",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__acme__find_employee",
                "tool_input": {"name": "Pat"},
                "tool_response": "Employee ID: E1\nEmployee ID: E2\n",
            },
        )
        self.hook(
            "claude",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__acme__find_employee",
                "tool_input": {"name": "Pat"},
                "tool_response": "Employee ID: E4\n",
            },
        )
        _, got = self.run_cli("get", "Pat")
        self.assertEqual(got["ids"]["employee"], "E4")
        self.assertNotIn("_raw", self.cache.read_text())

    def test_post_does_not_overwrite_an_id_or_demote_a_real_entry(self):
        self.run_cli("add", "person", "Ada Lovelace", "ids.employee=E1")
        self.hook(
            "claude",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__acme__find_employee",
                "tool_input": {"name": "Ada Lovelace"},
                "tool_response": "Employee ID: E2\nEmployee ID: E3\n",
            },
        )
        _, got = self.run_cli("get", "Ada")
        self.assertEqual(got["ids"]["employee"], "E1")
        self.assertNotIn("_stub", self.cache.read_text())

    def test_pre_allows_the_call_when_that_id_is_missing(self):
        self.run_cli("add", "person", "Ada Lovelace", "email=ada@acme.test")
        _, decision = self.hook(
            "claude",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "mcp__acme__find_employee",
                "tool_input": {"name": "Ada"},
            },
        )
        self.assertEqual(decision, {})

    def test_session_projection_omits_stubs_and_includes_pronouns(self):
        self.run_cli("add", "person", "Ada Lovelace", "pronouns=she/her", "ids.employee=E1")
        self.hook(
            "claude",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "mcp__acme__find_employee",
                "tool_input": {"name": "Pat"},
                "tool_response": "Employee ID: E1\nEmployee ID: E2\n",
            },
        )
        _, data = self.hook("claude", {"hook_event_name": "SessionStart"})
        text = data["hookSpecificOutput"]["additionalContext"]
        self.assertIn("pronouns=she/her", text)
        self.assertIn("ids.employee=E1", text)
        self.assertNotIn("pat", text.lower())
        self.assertIn("ask once this session", text)

    def test_cursor_pre_denies_with_permission(self):
        self.run_cli("add", "person", "Ada Lovelace", "pronouns=she/her", "ids.employee=E1")
        _, data = self.hook(
            "cursor",
            {
                "hook_event_name": "preToolUse",
                "tool_name": "mcp__acme__find_employee",
                "tool_input": {"name": "Ada"},
            },
        )
        self.assertEqual(data["permission"], "deny")
        self.assertIn("she/her", data["agent_message"])

    def test_unconfigured_tool_is_ignored(self):
        _, data = self.hook(
            "claude",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "mcp__other__lookup",
                "tool_input": {"name": "Ada"},
            },
        )
        self.assertEqual(data, {})

    def test_hooks_install_is_idempotent_and_uses_tool_matchers(self):
        code, data = self.run_cli("hooks", "install", "claude")
        self.assertEqual(code, 0)
        self.run_cli("hooks", "install", "claude")
        settings = json.loads((self.home / ".claude" / "settings.json").read_text())
        pre = settings["hooks"]["PreToolUse"]
        self.assertEqual(len(pre), 1)
        self.assertEqual(pre[0]["matcher"], "mcp__acme__find_employee")
        self.assertEqual(len(pre[0]["hooks"]), 1)
        self.assertIn("--tag alias", pre[0]["hooks"][0]["command"])
        session = settings["hooks"]["SessionStart"]
        self.assertEqual(session[0]["matcher"], "startup|resume|compact|clear|fork")
        _, status = self.run_cli("hooks", "status")
        self.assertIn("PreToolUse", status["claude"]["events"])
        self.run_cli("hooks", "uninstall", "claude")
        _, status = self.run_cli("hooks", "status")
        self.assertFalse(status["claude"]["installed"])

    def settings(self, platform):
        rel = Path(".claude") / "settings.json" if platform == "claude" else Path(".cursor") / "hooks.json"
        return self.home / rel

    def test_install_registers_the_same_events_as_before(self):
        self.run_cli("hooks", "install", "claude")
        claude = json.loads(self.settings("claude").read_text())["hooks"]
        self.assertEqual(sorted(claude), ["PostToolUse", "PreToolUse", "SessionStart"])
        self.assertEqual(claude["PostToolUse"][0]["matcher"], "mcp__acme__find_employee")
        self.run_cli("hooks", "install", "cursor")
        cursor = json.loads(self.settings("cursor").read_text())
        self.assertEqual(cursor["version"], 1)
        self.assertEqual(sorted(cursor["hooks"]), ["postToolUse", "preToolUse", "sessionStart"])

    def test_install_leaves_a_receipt_and_no_temp_file(self):
        self.run_cli("hooks", "install", "claude")
        receipt = json.loads((self.home / ".alias" / "hook-install.json").read_text())
        self.assertTrue(receipt["claude"]["created_file"])
        self.assertEqual(list(self.settings("claude").parent.glob("*.tmp")), [])
        self.assertEqual(list((self.home / ".alias").glob("*.tmp")), [])

    def test_uninstall_removes_a_settings_file_the_install_created(self):
        for platform in ("claude", "cursor"):
            self.run_cli("hooks", "install", platform)
            self.assertTrue(self.settings(platform).exists())
            self.run_cli("hooks", "uninstall", platform)
            self.assertFalse(self.settings(platform).exists(), platform)

    def test_uninstall_keeps_a_settings_file_it_did_not_create(self):
        path = self.settings("claude")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"theme": "dark"}))
        self.run_cli("hooks", "install", "claude")
        self.run_cli("hooks", "uninstall", "claude")
        self.assertEqual(json.loads(path.read_text()), {"theme": "dark"})

    def test_install_backs_up_an_existing_settings_file(self):
        path = self.settings("claude")
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"theme": "dark"}))
        self.run_cli("hooks", "install", "claude")
        backups = list((self.home / ".alias" / "backups").glob("claude-*.json"))
        self.assertEqual([json.loads(b.read_text()) for b in backups], [{"theme": "dark"}])

    def test_a_settings_file_that_is_not_json_is_refused_and_left_alone(self):
        path = self.settings("claude")
        path.parent.mkdir(parents=True)
        path.write_text("{oops")
        code, data = self.run_cli("hooks", "install", "claude")
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", data["error"])
        self.assertEqual(path.read_text(), "{oops")

    def test_extract_must_have_one_group(self):
        self.config.write_text(
            "cache: {cache}\ntools:\n  - tool: t\n    query: q\n    type: person\n    id: employee\n    extract: 'no group'\n".format(
                cache=self.cache
            )
        )
        code, data = self.run_cli("get", "ada")
        self.assertEqual(code, 1)
        self.assertIn("one capture group", data["error"])


if __name__ == "__main__":
    unittest.main()
