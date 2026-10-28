#!/usr/bin/env python3
"""Install, uninstall and status against a temporary home, for both adapters."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hooks_host as host  # noqa: E402

EVENTS = {
    "cursor": [host.Event("sessionStart"), host.Event("stop", extra={"loop_limit": 1})],
    "claude": [host.Event("SessionStart", matcher="startup|resume"), host.Event("UserPromptSubmit")],
}


class HostContract(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.spec = host.Spec(tag="demo", state_dir=self.home / ".demo", script=self.home / "demo.py",
                              events=EVENTS)
        self.other = host.Spec(tag="other", state_dir=self.home / ".other", script=self.home / "other.py",
                               events=EVENTS)

    def settings(self, platform):
        return host.settings_path(self.home, platform)

    def each(self):
        for platform in host.PLATFORMS:
            with self.subTest(platform=platform):
                yield platform

    def test_install_writes_the_events_and_a_receipt(self):
        for platform in self.each():
            result = host.install(self.spec, self.home, platform)
            self.assertTrue(result["installed"])
            events = host.status(self.spec, self.home)[platform]["events"]
            self.assertEqual(sorted(events), sorted(e.name for e in EVENTS[platform]))
            receipt = json.loads((self.spec.state_dir / "hook-install.json").read_text())
            self.assertTrue(receipt[platform]["created_file"])

    def test_install_twice_adds_nothing_new(self):
        for platform in self.each():
            host.install(self.spec, self.home, platform)
            first = self.settings(platform).read_text()
            host.install(self.spec, self.home, platform)
            self.assertEqual(self.settings(platform).read_text(), first)

    def test_uninstall_removes_a_file_the_install_created(self):
        for platform in self.each():
            host.install(self.spec, self.home, platform)
            host.uninstall(self.spec, self.home, platform)
            self.assertFalse(self.settings(platform).exists())
            self.assertFalse(host.status(self.spec, self.home)[platform]["installed"])

    def test_uninstall_keeps_other_entries_and_an_existing_file(self):
        keep = {"cursor": {"hooks": {"stop": [{"command": "echo keep"}]}},
                "claude": {"theme": "dark", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo keep"}]}]}}}
        for platform in self.each():
            path = self.settings(platform)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(keep[platform]))
            host.install(self.spec, self.home, platform)
            host.uninstall(self.spec, self.home, platform)
            self.assertEqual(json.loads(path.read_text()), keep[platform])

    def test_a_second_tag_is_left_alone(self):
        for platform in self.each():
            host.install(self.spec, self.home, platform)
            host.install(self.other, self.home, platform)
            host.uninstall(self.spec, self.home, platform)
            self.assertFalse(host.status(self.spec, self.home)[platform]["installed"])
            self.assertTrue(host.status(self.other, self.home)[platform]["installed"])

    def test_install_takes_a_backup_of_an_existing_file(self):
        for platform in self.each():
            path = self.settings(platform)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
            host.install(self.spec, self.home, platform)
            backups = list((self.spec.state_dir / "backups").glob(platform + "-*.json"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "{}")

    def test_writes_are_atomic_and_leave_no_temp_file(self):
        for platform in self.each():
            host.install(self.spec, self.home, platform)
            self.assertEqual(list(self.settings(platform).parent.glob("*.tmp")), [])
            self.assertEqual(list(self.spec.state_dir.glob("*.tmp")), [])

    def test_an_invalid_settings_file_is_refused_and_left_alone(self):
        for platform in self.each():
            path = self.settings(platform)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{not json")
            with self.assertRaises(host.HostError):
                host.install(self.spec, self.home, platform)
            self.assertEqual(path.read_text(), "{not json")
            self.assertIn("error", host.status(self.spec, self.home)[platform])

    def test_cursor_events_carry_their_extra_fields(self):
        host.install(self.spec, self.home, "cursor")
        data = json.loads(self.settings("cursor").read_text())
        self.assertEqual(data["version"], 1)
        self.assertEqual(data["hooks"]["stop"][0]["loop_limit"], 1)

    def test_claude_events_carry_their_matcher(self):
        host.install(self.spec, self.home, "claude")
        data = json.loads(self.settings("claude").read_text())
        self.assertEqual(data["hooks"]["SessionStart"][0]["matcher"], "startup|resume")
        self.assertNotIn("matcher", data["hooks"]["UserPromptSubmit"][0])

    def test_status_reports_nothing_installed_on_a_clean_home(self):
        report = host.status(self.spec, self.home)
        for platform in host.PLATFORMS:
            self.assertEqual(report[platform]["installed"], False)


    def test_reinstall_replaces_a_stale_command_instead_of_stacking(self):
        for platform in self.each():
            host.install(self.spec, self.home, platform)
            path = self.settings(platform)
            stale = path.read_text().replace(sys.executable, "/old/python")
            path.write_text(stale)
            host.install(self.spec, self.home, platform)
            text = path.read_text()
            self.assertNotIn("/old/python", text)
            events = host.status(self.spec, self.home)[platform]["events"]
            self.assertEqual(sorted(events), sorted(e.name for e in EVENTS[platform]))


if __name__ == "__main__":
    unittest.main()
