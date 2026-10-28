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


class PromotionCheckTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
