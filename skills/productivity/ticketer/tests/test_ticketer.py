#!/usr/bin/env python3
"""CLI tests for ticketer. No tracker, agent, or network is involved."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TICKETER = Path(__file__).resolve().parents[1] / "ticketer.py"

JIRA_TOML = """
tracker = "jira"
required = ["summary", "description", "issue_type", "labels", "customfield_10001"]
forbid_empty = ["labels"]
[defaults]
cloud_id = "acme.atlassian.net"
project_key = "PROJ"
components = ["Backend"]
[extra]
customfield_10001 = {id = "team-1"}
"""
GITHUB_TOML = """
tracker = "github"
required = ["summary", "description", "labels"]
forbid_empty = ["labels"]
[defaults]
repo = "acme/widgets"
"""
TASK_BODY = "## Context\nWhy this exists.\n\n## Acceptance criteria\n- [ ] Reset email is sent within one minute\n"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        (self.repo / ".ticketer").mkdir(parents=True)
        self.env = {
            **os.environ,
            "TICKETER_HOME": str(self.tmp / "home"),
            "TICKETER_CACHE": str(self.tmp / "cache"),
        }

    def write_config(self, toml, team="core"):
        (self.repo / ".ticketer" / "team").write_text(team + "\n")
        (self.repo / ".ticketer" / (team + ".toml")).write_text(toml)

    def run_cli(self, *args, stdin=None, cwd=None):
        proc = subprocess.run(
            [sys.executable, str(TICKETER), *args],
            input=json.dumps(stdin) if stdin is not None else None,
            text=True, capture_output=True, env=self.env, cwd=cwd or self.repo, check=False,
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, data, proc.stderr

    def draft(self, payload, *extra):
        return self.run_cli("draft", *extra, stdin=payload)


def jira_payload(**over):
    base = {"summary": "Send reset email", "description": TASK_BODY, "issue_type": "Task", "labels": ["Auth Flow"]}
    base.update(over)
    return base


class LocateTests(Base):
    def test_finds_repo_config_walking_up(self):
        self.write_config(JIRA_TOML)
        nested = self.repo / "a" / "b"
        nested.mkdir(parents=True)
        code, data, _ = self.run_cli("locate", cwd=nested)
        self.assertEqual(code, 0)
        self.assertEqual(data["team"], "core")
        self.assertTrue(data["config_exists"])

    def test_user_level_fallback(self):
        home = self.tmp / "home"
        home.mkdir()
        (home / "team").write_text("solo\n")
        (home / "solo.toml").write_text(GITHUB_TOML)
        code, data, _ = self.run_cli("locate", cwd=self.tmp)
        self.assertEqual(data["team"], "solo")
        self.assertTrue(data["config_exists"])

    def test_no_team_means_no_config_and_draft_fails_closed(self):
        code, data, _ = self.run_cli("locate", cwd=self.tmp)
        self.assertFalse(data["config_exists"])
        code, data, _ = self.draft(jira_payload(), "--cwd", str(self.tmp))
        self.assertEqual(code, 4)
        self.assertIn("fail closed", data["error"])

    def test_bad_slug_rejected(self):
        code, data, _ = self.run_cli("locate", "--team", "../etc")
        self.assertEqual(code, 4)

    def test_old_python_guard(self):
        src = TICKETER.read_text()
        self.assertLess(src.index("sys.version_info < (3, 11)"), src.index("import tomllib"))


class ConfigTests(Base):
    def test_unknown_key_and_placeholder_rejected(self):
        self.write_config('tracker = "jira"\nbogus = 1\n[defaults]\ncloud_id = "REPLACE_ME"\n')
        code, data, _ = self.draft(jira_payload())
        self.assertEqual(code, 4)
        codes = {e["code"] for e in data["errors"]}
        self.assertEqual(codes, {"unknown_config_key", "placeholder"})

    def test_bad_default_for_tracker(self):
        self.write_config('tracker = "github"\n[defaults]\nproject_key = "X"\n')
        code, data, _ = self.draft({"summary": "x"})
        self.assertEqual(code, 4)
        self.assertEqual(data["errors"][0]["code"], "bad_default")

    def test_init_writes_config_that_refuses_until_filled(self):
        code, data, _ = self.run_cli("init", "--team", "core", "--tracker", "jira", "--scope", "repo")
        self.assertEqual(code, 0)
        code, data, _ = self.draft(jira_payload())
        self.assertEqual(code, 4)
        self.assertTrue(all(e["code"] == "placeholder" for e in data["errors"]))
        code, _, _ = self.run_cli("init", "--team", "core", "--tracker", "jira", "--scope", "repo")
        self.assertEqual(code, 5)


class JiraDraftTests(Base):
    def setUp(self):
        super().setUp()
        self.write_config(JIRA_TOML)

    def test_valid_draft_normalizes_labels_and_merges_defaults(self):
        code, data, _ = self.draft(jira_payload())
        self.assertEqual(code, 0, data)
        self.assertIn("labels: auth-flow", data["render"])
        self.assertIn("components: Backend", data["render"])
        self.assertIn("customfield_10001", data["render"])
        self.assertTrue(any("normalized" in n for n in data["notes"]))

    def test_missing_required_and_empty_labels(self):
        code, data, _ = self.draft(jira_payload(labels=[]))
        self.assertEqual(code, 2)
        fields = {(e["code"], e["field"]) for e in data["errors"]}
        self.assertIn(("required_missing", "labels"), fields)
        self.assertIn(("forbidden_empty", "labels"), fields)

    def test_template_section_must_be_nonempty(self):
        code, data, _ = self.draft(jira_payload(description="## Context\n\n## Acceptance criteria\n- [ ] one thing happens here\n"))
        self.assertEqual(code, 2)
        self.assertEqual(data["errors"][0]["code"], "empty_section")

    def test_description_and_ac_must_not_repeat(self):
        line = "Reset email is sent within one minute"
        body = "## Context\n- %s\n\n## Acceptance criteria\n- [ ] %s\n" % (line, line)
        code, data, _ = self.draft(jira_payload(description=body))
        self.assertEqual(code, 2)
        self.assertEqual(data["errors"][0]["code"], "duplicate_content")

    def test_unknown_key_and_wrong_type_refused(self):
        code, data, _ = self.draft(jira_payload(bogus=1))
        self.assertEqual(code, 2)
        code, data, _ = self.draft(jira_payload(labels="auth"))
        self.assertEqual(code, 2)

    def test_standard_field_in_fields_is_misplaced(self):
        code, data, _ = self.draft(jira_payload(fields={"labels": ["x"]}))
        self.assertEqual(code, 2)
        self.assertTrue(any(e["code"] == "misplaced_field" for e in data["errors"]))

    def test_subtask_needs_parent(self):
        code, data, _ = self.draft(jira_payload(issue_type="Sub-task"))
        self.assertEqual(code, 2)
        self.assertTrue(any(e["field"] == "parent" for e in data["errors"]))

    def test_ai_disclosure_prepended_once(self):
        self.write_config(JIRA_TOML + "\n", team="core")
        text = JIRA_TOML.replace('tracker = "jira"', 'tracker = "jira"\nai_disclosure = "_AI generated._"')
        self.write_config(text)
        code, data, _ = self.draft(jira_payload())
        self.assertEqual(code, 0)
        self.assertIn("description:\n_AI generated._\n\n## Context", data["render"])


class JiraMetadataTests(Base):
    def setUp(self):
        super().setUp()
        self.write_config(JIRA_TOML)

    def store(self, kind, raw, issue_type=None):
        args = ["metadata", "store", "--tracker", "jira", "--scope", "PROJ", "--kind", kind]
        if issue_type:
            args += ["--issue-type", issue_type]
        return self.run_cli(*args, stdin=raw)

    def test_needs_listed_when_metadata_absent(self):
        code, data, _ = self.draft(jira_payload())
        self.assertEqual(code, 0)
        self.assertTrue(any(n["operation"] == "jira.get_project_issue_types" for n in data["needs"]))
        self.assertTrue(any("not checked" in w for w in data["warnings"]))

    def test_unknown_issue_type_and_tracker_required_field(self):
        self.store("issue-types", {"issueTypes": [{"name": "Task"}, {"name": "Bug"}]})
        self.store("fields", {"fields": [
            {"fieldId": "summary", "required": True, "name": "Summary"},
            {"fieldId": "priority", "required": True, "name": "Priority", "allowedValues": [{"name": "High"}, {"name": "Low"}]},
        ]}, "Task")
        code, data, _ = self.draft(jira_payload(issue_type="Epic"))
        self.assertEqual(code, 2)
        self.assertTrue(any(e["code"] == "unknown_issue_type" for e in data["errors"]))
        code, data, _ = self.draft(jira_payload())
        self.assertTrue(any(e["code"] == "tracker_required" and e["field"] == "priority" for e in data["errors"]))
        code, data, _ = self.draft(jira_payload(priority="Urgent"))
        self.assertTrue(any(e["code"] == "bad_value" for e in data["errors"]))
        code, data, _ = self.draft(jira_payload(priority="High"))
        self.assertEqual(code, 0, data)

    def test_require_metadata_blocks_without_cache(self):
        self.write_config(JIRA_TOML.replace('tracker = "jira"', 'tracker = "jira"\nrequire_metadata = true'))
        code, data, _ = self.draft(jira_payload())
        self.assertEqual(code, 2)
        self.assertTrue(any(e["code"] == "metadata_missing" for e in data["errors"]))


class SubmitGateTests(Base):
    def setUp(self):
        super().setUp()
        self.write_config(JIRA_TOML)
        _, self.drafted, _ = self.draft(jira_payload(priority="High", parent="PROJ-9"))
        self.id = self.drafted["id"]

    def test_wrong_token_refused(self):
        code, data, _ = self.run_cli("submit", "--draft", self.id, "--confirm", "nope")
        self.assertEqual(code, 2)
        self.assertNotIn("descriptor", data)

    def test_submit_emits_neutral_descriptor_with_jira_field_placement(self):
        code, data, _ = self.run_cli("submit", "--draft", self.id, "--confirm", self.id)
        self.assertEqual(code, 0, data)
        desc = data["descriptor"]
        self.assertEqual(desc["operation"], "jira.create_issue")
        payload = desc["payload"]
        self.assertEqual(payload["parent"], "PROJ-9")
        self.assertEqual(payload["projectKey"], "PROJ")
        self.assertNotIn("labels", payload)
        self.assertEqual(payload["additional_fields"]["labels"], ["auth-flow"])
        self.assertEqual(payload["additional_fields"]["priority"], {"name": "High"})
        self.assertEqual(payload["additional_fields"]["components"], [{"name": "Backend"}])
        self.assertNotIn("mcp__", json.dumps(data))

    def test_second_submit_refused_without_resend(self):
        self.run_cli("submit", "--draft", self.id, "--confirm", self.id)
        code, _, _ = self.run_cli("submit", "--draft", self.id, "--confirm", self.id)
        self.assertEqual(code, 2)
        code, _, _ = self.run_cli("submit", "--draft", self.id, "--confirm", self.id, "--resend")
        self.assertEqual(code, 0)

    def test_identical_redraft_after_emit_refused(self):
        self.run_cli("submit", "--draft", self.id, "--confirm", self.id)
        code, data, _ = self.draft(jira_payload(priority="High", parent="PROJ-9"))
        self.assertEqual(code, 2)
        self.assertIn("already emitted", data["error"])
        code, data, _ = self.draft(jira_payload(priority="High", parent="PROJ-9"), "--allow-duplicate")
        self.assertEqual(code, 0)

    def test_config_change_invalidates_draft(self):
        path = self.repo / ".ticketer" / "core.toml"
        path.write_text(path.read_text() + "\n# edited\n")
        code, data, _ = self.run_cli("submit", "--draft", self.id, "--confirm", self.id)
        self.assertEqual(code, 2)
        self.assertIn("config changed", data["error"])

    def test_expired_draft_refused(self):
        record = Path(self.env["TICKETER_CACHE"]) / "drafts" / ("%s.json" % self.id)
        data = json.loads(record.read_text())
        data["created_at"] -= 10 * 3600
        record.write_text(json.dumps(data))
        code, out, _ = self.run_cli("submit", "--draft", self.id, "--confirm", self.id)
        self.assertEqual(code, 2)
        self.assertIn("older than", out["error"])

    def test_malformed_id_cannot_escape_cache(self):
        code, data, _ = self.run_cli("submit", "--draft", "../../etc/passwd", "--confirm", "x")
        self.assertEqual(code, 5)


class VerifyTests(Base):
    def test_jira_diff_catches_dropped_component(self):
        self.write_config(JIRA_TOML)
        _, drafted, _ = self.draft(jira_payload())
        i = drafted["id"]
        self.run_cli("submit", "--draft", i, "--confirm", i)
        bad = {"key": "PROJ-10", "fields": {"summary": "Send reset email", "issuetype": {"name": "Task"},
               "labels": ["auth-flow"], "components": [], "description": "x"}}
        code, data, _ = self.run_cli("verify", "--draft", i, "--result", "-", stdin=bad)
        self.assertEqual(code, 2)
        self.assertEqual([m["field"] for m in data["mismatches"]], ["components"])
        good = {**bad, "fields": {**bad["fields"], "components": [{"name": "Backend"}]}}
        code, data, _ = self.run_cli("verify", "--draft", i, "--result", "-", stdin=good)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["ref"], "PROJ-10")

    def test_verify_requires_submit_first(self):
        self.write_config(JIRA_TOML)
        _, drafted, _ = self.draft(jira_payload())
        code, _, _ = self.run_cli("verify", "--draft", drafted["id"], "--result", "-", stdin={})
        self.assertEqual(code, 5)


class JiraUpdateTests(Base):
    def setUp(self):
        super().setUp()
        self.write_config(JIRA_TOML)

    def test_update_needs_key_and_a_change(self):
        code, data, _ = self.draft({"operation": "update"})
        self.assertEqual(code, 2)
        codes = {e["code"] for e in data["errors"]}
        self.assertEqual(codes, {"required_missing", "no_changes"})

    def test_update_does_not_apply_create_defaults_or_required(self):
        code, data, _ = self.draft({"operation": "update", "key": "PROJ-5", "labels": ["Needs Triage"]})
        self.assertEqual(code, 0, data)
        self.assertNotIn("components", data["render"])
        i = data["id"]
        _, out, _ = self.run_cli("submit", "--draft", i, "--confirm", i)
        self.assertEqual(out["descriptor"]["operation"], "jira.edit_issue")
        self.assertEqual(out["descriptor"]["payload"]["fields"]["labels"], ["needs-triage"])

    def test_update_cannot_blank_forbidden_field(self):
        code, data, _ = self.draft({"operation": "update", "key": "PROJ-5", "labels": []})
        self.assertEqual(code, 2)
        self.assertTrue(any(e["code"] == "forbidden_empty" for e in data["errors"]))

    def test_bad_key_format(self):
        code, data, _ = self.draft({"operation": "update", "key": "proj5", "summary": "x"})
        self.assertEqual(code, 2)
        self.assertTrue(any(e["code"] == "bad_format" for e in data["errors"]))

    def test_find_parent_escapes_quotes(self):
        code, data, _ = self.run_cli("find-parent", "--query", 'a" OR project = X')
        self.assertEqual(code, 0)
        jql = data["descriptor"]["payload"]["jql"]
        self.assertEqual(jql.count('"'), 2)
        self.assertIn("issuetype = Epic", jql)


class GithubTests(Base):
    def setUp(self):
        super().setUp()
        self.write_config(GITHUB_TOML, team="oss")

    def test_create_and_label_check_against_metadata(self):
        payload = {"summary": "Fix crash", "description": "## Context\nBroken.\n", "labels": ["bug"]}
        code, data, _ = self.draft(payload)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["needs"][0]["operation"], "github.list_labels")
        self.run_cli("metadata", "store", "--tracker", "github", "--scope", "acme/widgets", "--kind", "labels",
                     stdin=[{"name": "enhancement"}])
        code, data, _ = self.draft(payload)
        self.assertEqual(code, 2)
        self.assertEqual(data["errors"][0]["code"], "unknown_label")

    def test_descriptor_and_verify(self):
        payload = {"summary": "Fix crash", "description": "## Context\nBroken.\n", "labels": ["bug"], "assignees": ["octocat"]}
        _, drafted, _ = self.draft(payload)
        i = drafted["id"]
        _, out, _ = self.run_cli("submit", "--draft", i, "--confirm", i)
        desc = out["descriptor"]
        self.assertEqual(desc["operation"], "github.create_issue")
        self.assertEqual(desc["payload"]["title"], "Fix crash")
        self.assertTrue(Path(desc["payload"]["body_file"]).is_file())
        result = {"number": 7, "html_url": "https://github.com/acme/widgets/issues/7", "title": "Fix crash",
                  "body": "## Context\nBroken.", "labels": [{"name": "Bug"}], "assignees": [{"login": "octocat"}]}
        code, data, _ = self.run_cli("verify", "--draft", i, "--result", "-", stdin=result)
        self.assertEqual(code, 0, data)
        self.assertTrue(data["ref"].endswith("/7"))

    def test_find_parent_unsupported(self):
        code, data, _ = self.run_cli("find-parent", "--query", "x")
        self.assertEqual(code, 2)

    def test_bad_repo_and_key(self):
        code, data, _ = self.draft({"summary": "x", "description": "d", "labels": ["a"], "repo": "nope"})
        self.assertEqual(code, 2)
        code, data, _ = self.draft({"operation": "update", "key": "PROJ-1", "summary": "x"})
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
