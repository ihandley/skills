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

    def test_user_level_team_pointer_is_ignored(self):
        home = self.tmp / "home"
        home.mkdir()
        (home / "team").write_text("solo\n")
        (home / "solo.toml").write_text(GITHUB_TOML)
        code, data, _ = self.run_cli("locate", cwd=self.tmp)
        self.assertIsNone(data["team"])
        self.assertFalse(data["config_exists"])

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


class MappingTests(Base):
    def setUp(self):
        super().setUp()
        self.home = self.tmp / "home"
        self.home.mkdir()
        (self.home / "jira.toml").write_text(JIRA_TOML)
        (self.home / "github.toml").write_text(GITHUB_TOML)
        self.work = self.tmp / "work"
        self.proj = self.work / "proj"
        self.proj.mkdir(parents=True)

    def mappings(self, text):
        (self.home / "mappings.toml").write_text(text)

    def test_longest_path_prefix_wins_and_match_is_reported(self):
        self.mappings('[[mapping]]\npath = "%s"\nprovider = "jira"\n\n'
                      '[[mapping]]\npath = "%s"\nprovider = "github"\n' % (self.work, self.proj))
        _, data, _ = self.run_cli("locate", cwd=self.proj)
        self.assertEqual(data["team"], "github")
        self.assertTrue(data["mapping"].endswith("work/proj"), data["mapping"])
        _, data, _ = self.run_cli("locate", cwd=self.work)
        self.assertEqual(data["team"], "jira")
        self.assertTrue(data["config_exists"])

    def test_sibling_prefix_does_not_match(self):
        sibling = self.tmp / "work-other"
        sibling.mkdir()
        self.mappings('[[mapping]]\npath = "%s"\nprovider = "jira"\n' % self.work)
        _, data, _ = self.run_cli("locate", cwd=sibling)
        self.assertIsNone(data["team"])

    def test_remote_matches_when_no_path_does(self):
        other = self.tmp / "elsewhere"
        other.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=other, check=True)
        subprocess.run(["git", "remote", "add", "origin", "git@github.com:Acme/Widgets.git"], cwd=other, check=True)
        self.mappings('[[mapping]]\nremote = "acme/widgets"\nprovider = "github"\n')
        _, data, _ = self.run_cli("locate", cwd=other)
        self.assertEqual(data["team"], "github")
        _, data, _ = self.run_cli("locate", cwd=self.tmp)
        self.assertIsNone(data["team"])

    def test_unmapped_path_has_no_config_no_default_and_asks(self):
        self.mappings('[[mapping]]\npath = "%s"\nprovider = "jira"\n' % self.work)
        outside = self.tmp / "outside"
        outside.mkdir()
        _, data, _ = self.run_cli("locate", cwd=outside)
        self.assertFalse(data["config_exists"])
        self.assertIsNone(data["mapping"])
        self.assertEqual(data["providers"], ["github", "jira"])
        code, data, _ = self.draft(jira_payload(), "--cwd", str(outside))
        self.assertEqual(code, 4)
        self.assertIn("no default", data["error"])
        self.assertIn("map add", data["error"])

    def test_repo_level_team_file_beats_mapping(self):
        self.mappings('[[mapping]]\npath = "%s"\nprovider = "jira"\n' % self.tmp)
        self.write_config(GITHUB_TOML, team="oss")
        _, data, _ = self.run_cli("locate")
        self.assertEqual(data["team"], "oss")

    def test_overrides_reach_the_draft(self):
        self.mappings('[[mapping]]\npath = "%s"\nprovider = "github"\n'
                      '[mapping.overrides.defaults]\nrepo = "acme/special"\nlabels = ["triage"]\n' % self.proj)
        code, data, _ = self.draft({"summary": "x", "description": "y", "labels": ["bug"]}, "--cwd", str(self.proj))
        self.assertEqual(code, 0, data)
        self.assertIn("repo: acme/special", data["render"])
        self.assertIn("triage, bug", data["render"])

    def test_changed_overrides_invalidate_a_draft(self):
        text = ('[[mapping]]\npath = "%s"\nprovider = "github"\n'
                '[mapping.overrides.defaults]\nrepo = "acme/special"\n' % self.proj)
        self.mappings(text)
        _, data, _ = self.draft({"summary": "x", "description": "y", "labels": ["bug"]}, "--cwd", str(self.proj))
        self.mappings(text.replace("special", "other"))
        code, out, _ = self.run_cli("submit", "--draft", data["id"], "--confirm", data["id"])
        self.assertEqual(code, 2)
        self.assertIn("changed", out["error"])

    def test_invalid_mappings_file_is_rejected(self):
        self.mappings('[[mapping]]\nprovider = "jira"\nbogus = 1\n[mapping.overrides]\ntracker = "github"\n')
        code, data, _ = self.run_cli("locate", cwd=self.proj)
        self.assertEqual(code, 4)
        codes = {e["code"] for e in data["errors"]}
        self.assertEqual(codes, {"unknown_mapping_key", "empty_mapping", "bad_override"})

    def test_map_add_appends_keeps_comments_and_refuses_duplicates(self):
        self.mappings("# keep me\n[[mapping]]\npath = \"%s\"\nprovider = \"jira\"\n" % self.work)
        code, data, _ = self.run_cli("map", "add", "--path", str(self.proj), "--provider", "github")
        self.assertEqual(code, 0, data)
        text = (self.home / "mappings.toml").read_text()
        self.assertIn("# keep me", text)
        _, data, _ = self.run_cli("locate", cwd=self.proj)
        self.assertEqual(data["team"], "github")
        code, data, _ = self.run_cli("map", "add", "--path", str(self.proj), "--provider", "jira")
        self.assertEqual(code, 5)
        self.assertIn("--force", data["error"])
        _, data, _ = self.run_cli("locate", cwd=self.proj)
        self.assertEqual(data["team"], "github")

    def test_map_add_force_replaces_but_keeps_overrides(self):
        self.mappings('[[mapping]]\npath = "%s"\nprovider = "github"\n'
                      '[mapping.overrides.defaults]\nrepo = "acme/special"\n' % self.proj)
        code, data, _ = self.run_cli("map", "add", "--path", str(self.proj), "--provider", "jira", "--force")
        self.assertEqual(code, 0, data)
        self.assertTrue(data["replaced"])
        _, data, _ = self.run_cli("locate", cwd=self.proj)
        self.assertEqual(data["team"], "jira")
        self.assertEqual(data["overrides"], {"defaults": {"repo": "acme/special"}})

    def test_map_add_creates_file_and_needs_an_existing_provider(self):
        code, data, _ = self.run_cli("map", "add", "--path", str(self.proj), "--provider", "nope")
        self.assertEqual(code, 5)
        self.assertIn("init", data["error"])
        code, _, _ = self.run_cli("map", "add", "--path", str(self.proj), "--provider", "jira")
        self.assertEqual(code, 0)
        self.assertTrue((self.home / "mappings.toml").is_file())

    def test_init_user_scope_names_config_by_provider_and_writes_no_pointer(self):
        (self.home / "github.toml").unlink()
        code, data, _ = self.run_cli("init", "--tracker", "github")
        self.assertEqual(code, 0, data)
        self.assertTrue((self.home / "github.toml").is_file())
        self.assertIsNone(data["team_pointer"])
        self.assertFalse((self.home / "team").exists())
        self.assertIn("map add", data["next"])


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


class RequiredByTypeTests(Base):
    def setUp(self):
        super().setUp()
        self.write_config(JIRA_TOML + '[required_by_type]\nbug = ["customfield_10568", "customfield_10676"]\n')

    def missing(self, data):
        return {e["field"] for e in (data or {}).get("errors", []) if e["code"] == "required_missing"}

    def test_matching_type_requires_extra_fields_case_insensitively(self):
        code, data, _ = self.draft(jira_payload(issue_type="Bug"))
        self.assertEqual(code, 2)
        self.assertEqual(self.missing(data), {"customfield_10568", "customfield_10676"})

    def test_extra_fields_satisfied_by_fields(self):
        fields = {"customfield_10568": {"id": "1"}, "customfield_10676": {"id": "2"}}
        code, data, _ = self.draft(jira_payload(issue_type="Bug", fields=fields))
        self.assertEqual(self.missing(data), set())

    def test_other_types_do_not_require_them(self):
        code, data, _ = self.draft(jira_payload(issue_type="Task"))
        self.assertEqual(self.missing(data), set())

    def test_bad_shape_is_a_config_error(self):
        self.write_config(JIRA_TOML + '[required_by_type]\nbug = "customfield_10568"\n')
        code, data, _ = self.draft(jira_payload())
        self.assertEqual(code, 4)
        self.assertEqual(data["errors"][0]["code"], "bad_type")


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

    def store_select(self):
        self.store("fields", {"fields": [
            {"fieldId": "customfield_1", "required": False, "name": "Team",
             "allowedValues": [{"id": "123", "value": "Core"}, {"id": "456", "value": "Edge"}]},
        ]}, "Task")

    def test_id_form_select_value_validates_against_option_id(self):
        self.store_select()
        code, data, _ = self.draft(jira_payload(fields={"customfield_1": {"id": "123"}}))
        self.assertEqual(code, 0, data)

    def test_name_form_select_value_still_validates(self):
        self.store_select()
        code, data, _ = self.draft(jira_payload(fields={"customfield_1": {"value": "Edge"}}))
        self.assertEqual(code, 0, data)

    def test_unknown_id_fails_and_lists_allowed_names(self):
        self.store_select()
        code, data, _ = self.draft(jira_payload(fields={"customfield_1": {"id": "999"}}))
        self.assertEqual(code, 2)
        error = next(e for e in data["errors"] if e["code"] == "bad_value")
        self.assertIn("Core", error["message"])
        self.assertIn("Edge", error["message"])

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
