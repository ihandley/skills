#!/usr/bin/env python3
"""Each test breaks a copy of this repo one way and expects the check to say so."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import promotion  # noqa: E402

REPO = HERE.parent.parent
KEEP = ("README.md", ".agents", ".claude-plugin", "docs", "skills")
SKIP = shutil.ignore_patterns("__pycache__", ".stepper", ".claude", "node_modules", "*.pyc")


class RepoCopy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for name in KEEP:
            src = REPO / name
            if src.is_dir():
                shutil.copytree(src, self.tmp / name, ignore=SKIP)
            else:
                shutil.copy(src, self.tmp / name)

    def edit(self, rel, fn):
        path = self.tmp / rel
        path.write_text(fn(path.read_text(encoding="utf-8")), encoding="utf-8")



class PromotionCheckTests(RepoCopy):
    def assert_reports(self, needle):
        problems = promotion.check(self.tmp)
        self.assertTrue(any(needle in p for p in problems), problems)

    def test_this_repo_passes(self):
        self.assertEqual(promotion.check(REPO), [])

    def test_manifest_missing_a_promoted_skill(self):
        def drop(text):
            data = json.loads(text)
            data["skills"].remove("./skills/engineering/deslop")
            return json.dumps(data)
        self.edit(".claude-plugin/plugin.json", drop)
        self.assert_reports("plugin.json: missing ./skills/engineering/deslop")

    def test_manifest_listing_a_skill_that_is_not_promoted(self):
        def add(text):
            data = json.loads(text)
            data["skills"].append("./skills/engineering/ghost")
            return json.dumps(data)
        self.edit(".claude-plugin/plugin.json", add)
        self.assert_reports("ghost")

    def test_readme_groups_skill_under_wrong_invocation_heading(self):
        line = next(l for l in (REPO / "skills/engineering/README.md").read_text().splitlines()
                    if l.startswith("- **[deslop]"))
        def move(text):
            return text.replace(line + "\n", "").replace("## User-invoked\n", "## User-invoked\n\n" + line + "\n", 1)
        self.edit("skills/engineering/README.md", move)
        self.assert_reports("deslop is under user-invoked, its mode is model-invoked")

    def test_frontmatter_and_agent_manifest_disagree(self):
        self.edit("skills/engineering/pair/agents/openai.yaml",
                  lambda t: t.replace("allow_implicit_invocation: false", "allow_implicit_invocation: true"))
        self.assert_reports("pair: SKILL.md says user-invoked, agents/openai.yaml says model-invoked")

    def test_docs_page_missing_a_section(self):
        self.edit("docs/engineering/deslop.md", lambda t: t.replace("## Common questions", "## Questions"))
        self.assert_reports("docs/engineering/deslop.md: sections are")

    def test_docs_page_missing_entirely(self):
        (self.tmp / "docs/productivity/tidy.md").unlink()
        self.assert_reports("docs/productivity/tidy.md: missing")

    def test_install_commands_drift_from_the_canonical_block(self):
        self.edit("README.md", lambda t: t.replace("npx skills@latest add ihandley/skills\n",
                                                   "npx skills add ihandley/skills\n", 1))
        self.assert_reports("install command")

    def test_removed_skill_page_not_marked_archived(self):
        self.edit("docs/engineering/chad-learn.md", lambda t: t.replace("> **Archived.**", "> Old."))
        self.assert_reports("chad-learn.md: removed skill's page is not marked archived")

    def test_removed_skill_with_no_page(self):
        (self.tmp / "docs/engineering/chad-learn.md").unlink()
        self.assert_reports("chad-learn.md: removed skill has no archived page")

    def test_a_host_module_copy_that_differs(self):
        self.edit("skills/engineering/understand/hooks_host.py", lambda t: t + "# drift\n")
        self.assert_reports("hooks_host.py: differs from")

    def test_a_skill_missing_its_host_module(self):
        (self.tmp / "skills/productivity/alias/hooks_host.py").unlink()
        self.assert_reports("productivity/alias/hooks_host.py: missing")


class GenerateTests(RepoCopy):
    def generate(self):
        return promotion.generate(self.tmp)

    def test_generate_is_a_no_op_on_a_consistent_repo(self):
        self.assertEqual(self.generate(), [])

    def test_moving_a_skill_folder_then_generate_updates_every_list_and_check_passes(self):
        shutil.move(str(self.tmp / "skills/engineering/deslop"), str(self.tmp / "skills/productivity/deslop"))
        shutil.move(str(self.tmp / "docs/engineering/deslop.md"), str(self.tmp / "docs/productivity/deslop.md"))
        self.assertNotEqual(promotion.check(self.tmp), [])
        changed = self.generate()
        for rel in (".claude-plugin/plugin.json", "README.md", "skills/engineering/README.md",
                    "skills/productivity/README.md"):
            self.assertIn(rel, changed)
        self.assertEqual(promotion.check(self.tmp), [])
        manifest = json.loads((self.tmp / ".claude-plugin/plugin.json").read_text())
        self.assertIn("./skills/productivity/deslop", manifest["skills"])
        self.assertNotIn("./skills/engineering/deslop", manifest["skills"])

    def test_a_new_skill_gets_its_frontmatter_description_and_check_passes(self):
        new = self.tmp / "skills/productivity/newbie"
        (new / "agents").mkdir(parents=True)
        (new / "SKILL.md").write_text("---\nname: newbie\ndescription: Does a new thing.\n---\n")
        (new / "agents/openai.yaml").write_text("interface:\n  display_name: \"Newbie\"\n")
        (self.tmp / "docs/productivity/newbie.md").write_text(
            "## What it does\n\nx\n\n## When to reach for it\n\nx\n\n## Common questions\n\nx\n\n## It's working if\n\nx\n")
        self.generate()
        self.assertIn("**[newbie](./skills/productivity/newbie/SKILL.md)**: Does a new thing.",
                      (self.tmp / "README.md").read_text())
        self.assertEqual(promotion.check(self.tmp), [])

    def test_hand_written_prose_and_descriptions_are_left_alone(self):
        self.edit("README.md", lambda t: t.replace("Skills for daily code work.", "My own intro.", 1))
        self.edit("docs/engineering/deslop.md", lambda t: t + "\nExtra note.\n")
        before_skill = (self.tmp / "skills/engineering/deslop/SKILL.md").read_text()
        before_page = (self.tmp / "docs/engineering/deslop.md").read_text()
        self.generate()
        self.assertIn("My own intro.", (self.tmp / "README.md").read_text())
        self.assertEqual((self.tmp / "docs/engineering/deslop.md").read_text(), before_page)
        self.assertEqual((self.tmp / "skills/engineering/deslop/SKILL.md").read_text(), before_skill)

    def test_an_empty_group_reads_none_yet(self):
        shutil.move(str(self.tmp / "skills/engineering/deslop"), str(self.tmp / "skills/misc_deslop"))
        self.generate()
        self.assertNotIn("deslop", (self.tmp / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()
