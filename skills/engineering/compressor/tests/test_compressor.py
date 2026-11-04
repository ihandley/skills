#!/usr/bin/env python3
"""CLI tests for compressor. The script is the seam; nothing inside it is imported."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

COMPRESSOR = Path(__file__).resolve().parents[1] / "compressor.py"

DOCUMENT = """# Title

The history of this note is long and motivational.

Keep this fact.
"""
SHORTER = """# Title

Keep this fact.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *args, candidate=None, raw=None, cwd=None):
        if raw is not None:
            payload = raw
        elif candidate is not None:
            payload = json.dumps(candidate)
        else:
            payload = None
        proc = subprocess.run(
            [sys.executable, str(COMPRESSOR), *args],
            input=payload,
            text=True,
            capture_output=True,
            cwd=str(cwd or self.repo),
        )
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
        return proc.returncode, data, proc.stderr

    def write_skill_set(self, skill=None, notes=None):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL if skill is None else skill)
        (root / "notes.md").write_text(NOTES if notes is None else notes)
        return root


SKILL = """---
name: demo
description: Compress a demo skill.
---

# Demo

Read [the notes](notes.md) before answering.

The history of this skill is long motivational padding.

Keep the signal: refuse when the file is missing.
"""

SKILL_SHORT = """---
name: demo
description: Compress a demo skill.
---

# Demo

Read [the notes](notes.md) before answering.

Keep the signal: refuse when the file is missing.
"""

NOTES = "The note states one fact.\n"
NOTES_GROWN = "The note states one fact. The note states one fact.\n"


class DocumentTests(Base):
    def test_check_passes_a_shorter_document_and_leaves_bytes(self):
        path = self.repo / "note.md"
        path.write_text(DOCUMENT)
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": SHORTER})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertTrue(data["ok"])
        self.assertEqual(data["failures"], [])
        # "# Title" + the history sentence + "Keep this fact." = 14; the history sentence is 9 of them.
        self.assertEqual(data["words_before"], 14)
        self.assertEqual(data["words_after"], 5)
        self.assertEqual(data["files"], [{
            "path": "note.md",
            "disposition": "replaced",
            "words_before": 14,
            "words_after": 5,
        }])
        self.assertEqual(data["skipped"], [])
        self.assertEqual(data["unresolved"], [])
        self.assertIn("The history of this note is long and motivational.", data["diffs"]["note.md"])
        self.assertIsNone(data["description_chars_before"])
        self.assertIsNone(data["description_chars_after"])
        self.assertIsNone(data["description_cap"])
        self.assertIsNone(data["sibling_median"])
        self.assertEqual(path.read_text(), DOCUMENT)

    def test_apply_writes_the_shorter_document(self):
        path = self.repo / "note.md"
        path.write_text(DOCUMENT)
        code, data, err = self.run_cli("apply", "note.md", candidate={"note.md": SHORTER})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertTrue(data["ok"])
        self.assertEqual(path.read_text(), SHORTER)

    def test_apply_writes_nothing_when_gated_words_do_not_fall(self):
        path = self.repo / "note.md"
        path.write_text(DOCUMENT)
        code, data, err = self.run_cli("apply", "note.md", candidate={"note.md": DOCUMENT})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertFalse(data["ok"])
        self.assertEqual(data["failures"], ["word_total"])
        self.assertEqual(data["files"][0]["disposition"], "unchanged")
        self.assertEqual(data["diffs"], {})
        self.assertEqual(path.read_text(), DOCUMENT)

    def test_changed_inline_code_is_rejected(self):
        path = self.repo / "note.md"
        original = "# Title\n\nUse `KEEP_ME` and see https://example.com/a.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "# Title\n\nUse `CHANGED` and see https://example.com/a.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["protected_span"])
        self.assertEqual(path.read_text(), original)

    def test_changed_frontmatter_value_is_rejected(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\ntitle: Other\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["frontmatter_value"])
        self.assertEqual(path.read_text(), original)

    def test_unchanged_nested_frontmatter_mapping_passes(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\nmetadata:\n  author: Ada\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\ntitle: Note\nmetadata:\n  author: Ada\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["failures"], [])
        self.assertEqual(data["words_before"], 19)
        self.assertEqual(data["words_after"], 10)
        self.assertEqual(path.read_text(), original)

    def test_changed_nested_frontmatter_value_is_rejected(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\nmetadata:\n  author: Ada\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\ntitle: Note\nmetadata:\n  author: Grace\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["frontmatter_value"])
        self.assertEqual(path.read_text(), original)

    def test_unchanged_nested_frontmatter_list_passes(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\ntools:\n  - Bash\n  - Read\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\ntitle: Note\ntools:\n  - Bash\n  - Read\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["failures"], [])
        self.assertEqual(path.read_text(), original)

    def test_changed_nested_frontmatter_list_is_rejected(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\ntools:\n  - Bash\n  - Read\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\ntitle: Note\ntools:\n  - Bash\n  - Write\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["frontmatter_value"])
        self.assertEqual(path.read_text(), original)

    def test_unclosed_frontmatter_fails_parse(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\ntitle: Note\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["parse"])
        self.assertEqual(path.read_text(), original)

    def test_unparseable_frontmatter_line_fails_parse(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\nmetadata:\n  author: Ada\n  ::: nope\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["parse"])
        self.assertEqual(path.read_text(), original)

    def test_non_text_target_is_rejected_and_not_written(self):
        path = self.repo / "note.json"
        original = '{"title": "Note"}\n'
        path.write_text(original)
        code, data, err = self.run_cli("apply", "note.json", candidate={"note.json": "{}\n"})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["unsupported_type"])
        self.assertEqual(path.read_text(), original)

    def test_escaping_candidate_key_is_rejected(self):
        path = self.repo / "note.md"
        path.write_text(DOCUMENT)
        code, data, err = self.run_cli(
            "apply", "note.md", candidate={"../evil.md": "pwned\n", "note.md": SHORTER},
        )
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["escaping_key"])
        self.assertEqual(path.read_text(), DOCUMENT)
        self.assertFalse((self.repo.parent / "evil.md").exists())

    def test_unknown_candidate_key_is_rejected(self):
        path = self.repo / "note.md"
        path.write_text(DOCUMENT)
        code, data, err = self.run_cli(
            "apply", "note.md", candidate={"note.md": SHORTER, "extra.md": "nope\n"},
        )
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["unknown_key"])
        self.assertEqual(path.read_text(), DOCUMENT)
        self.assertFalse((self.repo / "extra.md").exists())

    def test_broken_heading_anchor_is_rejected(self):
        path = self.repo / "note.md"
        original = "# Keep This\n\nSee [the section](#keep-this).\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "See [the section](#keep-this).\n"
        quotes = {"# Keep This": "See [the section](#keep-this)."}
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate, "quotes": quotes})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["heading_anchor"])
        self.assertEqual(path.read_text(), original)

    def test_in_set_heading_anchor_uses_the_candidate_text(self):
        skill = (
            "---\nname: demo\ndescription: Demo skill.\n---\n\n# Demo\n\n"
            "Read [the notes](notes.md#kept-fact).\n\n"
            "The history of this skill is long motivational padding.\n\nKeep the signal.\n"
        )
        short = skill.replace("The history of this skill is long motivational padding.\n\n", "")
        notes = "# Kept Fact\n\nThe history of this note is long and motivational.\n"
        root = self.write_skill_set(skill, notes)
        code, data, err = self.run_cli(
            "check", "skills/engineering/demo",
            candidate={
                "SKILL.md": short,
                "notes.md": "The history of this note is long and motivational.\n",
                "quotes": {"# Kept Fact": "The history of this note is long and motivational."},
            },
        )
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["heading_anchor"])
        self.assertEqual((root / "SKILL.md").read_text(), skill)
        self.assertEqual((root / "notes.md").read_text(), notes)

    def test_duplicate_heading_slugs_gain_a_numeric_suffix(self):
        path = self.repo / "note.md"
        original = (
            "# Duplicate\n\n# Duplicate\n\n# Duplicate\n\n"
            "See [the first](#duplicate), [the second](#duplicate-1), and [the third](#duplicate-2).\n\n"
            "The history of this note is long and motivational.\n"
        )
        path.write_text(original)
        candidate = (
            "# Duplicate\n\n# Duplicate\n\n# Duplicate\n\n"
            "See [the first](#duplicate), [the second](#duplicate-1), and [the third](#duplicate-2).\n"
        )
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["failures"], [])
        self.assertEqual(path.read_text(), original)

    def test_unresolved_reference_is_listed_and_left_out(self):
        text = (
            "---\nname: demo\ndescription: Demo skill.\n---\n\n# Demo\n\n"
            "Read [the notes](notes.md). The shape lives in `templates/<issue-type>.md`.\n\n"
            "The history of this skill is long motivational padding.\n\nKeep the signal.\n"
        )
        short = text.replace("The history of this skill is long motivational padding.\n\n", "")
        root = self.write_skill_set(text, "One fact.\n")
        code, data, err = self.run_cli("check", "skills/engineering/demo", candidate={"SKILL.md": short})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["unresolved"], ["templates/<issue-type>.md"])
        self.assertEqual([item["path"] for item in data["files"]], ["SKILL.md", "notes.md"])
        self.assertEqual((root / "SKILL.md").read_text(), text)

    def test_non_text_support_file_is_skipped(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        text = (
            "---\nname: demo\ndescription: Demo skill.\n---\n\n# Demo\n\n"
            "Load [the schema](config.schema.json).\n\n"
            "The history of this skill is long motivational padding.\n\nKeep the signal.\n"
        )
        short = text.replace("The history of this skill is long motivational padding.\n\n", "")
        schema = '{"type": "object"}\n'
        (root / "SKILL.md").write_text(text)
        (root / "config.schema.json").write_text(schema)
        code, data, err = self.run_cli("check", "skills/engineering/demo", candidate={"SKILL.md": short})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["failures"], [])
        self.assertEqual(data["skipped"], ["config.schema.json"])
        self.assertEqual(data["files"][-1], {
            "path": "config.schema.json",
            "disposition": "skipped",
            "words_before": 0,
            "words_after": 0,
        })
        self.assertEqual((root / "config.schema.json").read_text(), schema)
        self.assertEqual((root / "SKILL.md").read_text(), text)


class SkillTests(Base):
    def test_check_passes_a_shorter_skill_and_leaves_an_unmentioned_support_file(self):
        root = self.write_skill_set()
        code, data, err = self.run_cli(
            "check", "skills/engineering/demo", candidate={"SKILL.md": SKILL_SHORT},
        )
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["failures"], [])
        # Description value "Compress a demo skill." is outside the word count: 34 tokens - 4 = 30, then the 9-word history sentence is gone.
        self.assertEqual(data["words_before"], 35)
        self.assertEqual(data["words_after"], 26)
        self.assertEqual(data["files"], [
            {"path": "SKILL.md", "disposition": "replaced", "words_before": 30, "words_after": 21},
            {"path": "notes.md", "disposition": "unchanged", "words_before": 5, "words_after": 5},
        ])
        self.assertEqual(data["description_chars_before"], 22)
        self.assertEqual(data["description_chars_after"], 22)
        self.assertEqual(data["description_cap"], 1024)
        self.assertIsNone(data["sibling_median"])
        self.assertEqual((root / "SKILL.md").read_text(), SKILL)
        self.assertEqual((root / "notes.md").read_text(), NOTES)

    def test_apply_rejects_a_support_file_whose_gated_words_grew(self):
        root = self.write_skill_set()
        code, data, err = self.run_cli(
            "apply", "skills/engineering/demo",
            candidate={"SKILL.md": SKILL_SHORT, "notes.md": NOTES_GROWN},
        )
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["word_growth"])
        self.assertEqual(data["words_before"], 35)
        self.assertEqual(data["words_after"], 31)
        self.assertEqual((root / "SKILL.md").read_text(), SKILL)
        self.assertEqual((root / "notes.md").read_text(), NOTES)

    def test_apply_writes_every_replaced_file_or_none(self):
        notes = "The note states one fact.\n\nThe history of this note is long and motivational.\n"
        root = self.write_skill_set(notes=notes)
        notes_short = "The note states one fact.\n"
        code, data, err = self.run_cli(
            "apply", "skills/engineering/demo",
            candidate={"SKILL.md": SKILL_SHORT, "notes.md": notes_short},
        )
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual([item["disposition"] for item in data["files"]], ["replaced", "replaced"])
        self.assertEqual((root / "SKILL.md").read_text(), SKILL_SHORT)
        self.assertEqual((root / "notes.md").read_text(), notes_short)

    def test_description_only_edit_fails_the_word_gate(self):
        long_skill = SKILL.replace("description: Compress a demo skill.", "description: Compress a demo skill. Use it often.")
        root = self.write_skill_set(skill=long_skill)
        described = SKILL
        code, data, err = self.run_cli("check", "skills/engineering/demo", candidate={"SKILL.md": described})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["word_total"])
        self.assertEqual(data["words_before"], 35)
        self.assertEqual(data["words_after"], 35)
        self.assertEqual(data["description_chars_before"], 36)
        self.assertEqual(data["description_chars_after"], 22)
        self.assertEqual((root / "SKILL.md").read_text(), long_skill)

    def test_description_over_1024_characters_is_rejected(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        text = (
            "---\nname: demo\ndescription: Demo skill.\n---\n\n"
            "Keep the signal.\n\nThe history of this skill is long motivational padding.\n"
        )
        text = text.replace("description: Demo skill.", "description: " + ("x" * 1025))
        described = text.replace("The history of this skill is long motivational padding.\n", "")
        (root / "SKILL.md").write_text(text)
        code, data, err = self.run_cli("check", "skills/engineering/demo", candidate={"SKILL.md": described})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["description_cap"])
        self.assertEqual(data["description_chars_after"], 1025)
        self.assertEqual(data["description_cap"], 1024)
        self.assertEqual((root / "SKILL.md").read_text(), text)

    def test_unlinked_readme_stays_out_of_the_set(self):
        root = self.write_skill_set()
        readme = "# Human\n\nThis page is for people.\n"
        (root / "README.md").write_text(readme)
        code, data, err = self.run_cli(
            "check", "skills/engineering/demo", candidate={"SKILL.md": SKILL_SHORT},
        )
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertNotIn("README.md", [item["path"] for item in data["files"]])
        self.assertNotIn("README.md", data["skipped"])
        self.assertNotIn("README.md", data["unresolved"])
        self.assertEqual((root / "README.md").read_text(), readme)
        self.assertEqual((root / "SKILL.md").read_text(), SKILL)

    def test_directory_without_skill_entry_is_rejected(self):
        folder = self.repo / "notes"
        folder.mkdir()
        (folder / "one.md").write_text("Keep this fact.\n")
        (folder / "two.md").write_text("Another fact.\n")
        code, data, err = self.run_cli("check", "notes", candidate={"one.md": "Keep this fact.\n"})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["not_a_skill_directory"])
        self.assertEqual((folder / "one.md").read_text(), "Keep this fact.\n")
        self.assertEqual((folder / "two.md").read_text(), "Another fact.\n")

    def test_skill_name_resolves_by_walking_up_to_skills(self):
        root = self.write_skill_set()
        nested = self.repo / "elsewhere"
        nested.mkdir()
        code, data, err = self.run_cli(
            "check", "demo", candidate={"SKILL.md": SKILL_SHORT}, cwd=nested,
        )
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual((root / "SKILL.md").read_text(), SKILL)

    def test_ambiguous_skill_name_is_rejected(self):
        for bucket in ("engineering", "productivity"):
            root = self.repo / "skills" / bucket / "demo"
            root.mkdir(parents=True)
            (root / "SKILL.md").write_text(SKILL)
        code, data, err = self.run_cli("check", "demo", candidate={"SKILL.md": SKILL_SHORT})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["ambiguous_skill"])

    def test_missing_skill_name_is_rejected(self):
        (self.repo / "skills" / "engineering").mkdir(parents=True)
        code, data, err = self.run_cli("check", "missing", candidate={})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["skill_not_found"])

    def test_skill_entry_file_path_resolves_to_the_skill(self):
        root = self.write_skill_set()
        code, data, err = self.run_cli(
            "check", "skills/engineering/demo/SKILL.md", candidate={"SKILL.md": SKILL_SHORT},
        )
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual([item["path"] for item in data["files"]], ["SKILL.md", "notes.md"])

    def test_folded_description_length_is_the_unfolded_scalar(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        text = (
            "---\nname: demo\ndescription: >-\n  alpha beta\n  gamma\n---\n\n"
            "Keep the signal.\n\nThe history of this skill is long motivational padding.\n"
        )
        short = text.replace("\n\nThe history of this skill is long motivational padding.\n", "\n")
        (root / "SKILL.md").write_text(text)
        code, data, err = self.run_cli("check", "skills/engineering/demo", candidate={"SKILL.md": short})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["description_chars_before"], 16)
        self.assertEqual(data["description_chars_after"], 16)

    def test_sibling_median_averages_the_two_central_lengths(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        text = "---\nname: demo\ndescription: Demo skill.\n---\n\nKeep the signal.\n\nPadding words that leave.\n"
        short = "---\nname: demo\ndescription: Demo skill.\n---\n\nKeep the signal.\n"
        (root / "SKILL.md").write_text(text)
        for name, length in (("left", 10), ("right", 11)):
            sibling = self.repo / "skills" / "engineering" / name
            sibling.mkdir()
            (sibling / "SKILL.md").write_text(
                "---\nname: %s\ndescription: %s\n---\n\nKeep.\n" % (name, "x" * length)
            )
        code, data, err = self.run_cli("check", "demo", candidate={"SKILL.md": short})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["sibling_median"], 10.5)

    def test_directory_link_includes_markdown_and_text_under_it(self):
        root = self.repo / "skills" / "engineering" / "demo"
        (root / "guides" / "nested").mkdir(parents=True)
        text = (
            "---\nname: demo\ndescription: Demo skill.\n---\n\n# Demo\n\n"
            "Read [the guides](guides/).\n\n"
            "The history of this skill is long motivational padding.\n\nKeep the signal.\n"
        )
        short = text.replace("The history of this skill is long motivational padding.\n\n", "")
        (root / "SKILL.md").write_text(text)
        (root / "guides" / "a.md").write_text("Alpha fact.\n")
        (root / "guides" / "b.txt").write_text("Beta fact.\n")
        (root / "guides" / "c.json").write_text("{}\n")
        (root / "guides" / "nested" / "d.md").write_text("Delta fact.\n")
        code, data, err = self.run_cli("check", "demo", candidate={"SKILL.md": short})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(
            [item["path"] for item in data["files"]],
            ["SKILL.md", "guides/a.md", "guides/b.txt", "guides/nested/d.md"],
        )
        self.assertEqual(data["skipped"], [])
        self.assertEqual((root / "guides" / "c.json").read_text(), "{}\n")


class PlainTextTests(Base):
    def test_plain_text_shrink_passes_without_a_structure_check(self):
        path = self.repo / "note.txt"
        original = "Keep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "Keep this fact.\n"
        code, data, err = self.run_cli("check", "note.txt", candidate={"note.txt": candidate})
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["failures"], [])
        self.assertIsNone(data["description_cap"])
        self.assertEqual(path.read_text(), original)

    def test_non_utf8_target_is_rejected(self):
        path = self.repo / "note.md"
        original = b"\xff\xfeKeep this fact.\n"
        path.write_bytes(original)
        code, data, err = self.run_cli("apply", "note.md", candidate={"note.md": "Keep this fact.\n"})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["not_utf8"])
        self.assertEqual(path.read_bytes(), original)

    def test_replacing_a_key_with_a_nested_mapping_is_a_key_change(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\nmetadata:\n  author: ada\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["frontmatter_keys"])
        self.assertEqual(path.read_text(), original)

    def test_unclosed_fence_fails_parse(self):
        path = self.repo / "note.md"
        original = "# Title\n\n```\nkeep\n```\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "# Title\n\n```\nkeep\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertIn("parse", data["failures"])
        self.assertEqual(path.read_text(), original)

    def test_frontmatter_keys_must_stay(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\ntitle: Note\nstatus: open\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["frontmatter_keys"])
        self.assertEqual(path.read_text(), original)

    def test_skill_name_value_must_stay(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL)
        renamed = SKILL_SHORT.replace("name: demo", "name: other")
        code, data, err = self.run_cli("check", "demo", candidate={"SKILL.md": renamed})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["frontmatter_value"])
        self.assertEqual((root / "SKILL.md").read_text(), SKILL)

    def test_bad_json_writes_nothing(self):
        path = self.repo / "note.md"
        path.write_text(DOCUMENT)
        code, data, err = self.run_cli("apply", "note.md", raw="not-json")
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["bad_json"])
        self.assertEqual(path.read_text(), DOCUMENT)

    def test_wrong_arity_writes_nothing(self):
        path = self.repo / "note.md"
        path.write_text(DOCUMENT)
        code, data, err = self.run_cli("check", "note.md", "extra", candidate={"note.md": SHORTER})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["wrong_arity"])
        self.assertEqual(path.read_text(), DOCUMENT)


INVENTORY_DOC = """# Title

The history of this note is long and motivational.

Keep this fact.

- a list item

| a | b |
|---|---|
| 1 | 2 |

```
code
```

Use `x` here.

Visit https://example.com/a for more.

Nothing ends this line

Repeated padding sentence here.

Repeated padding sentence here.
"""


class InventoryTests(Base):
    def inventory(self, text, *extra):
        (self.repo / "note.md").write_text(text)
        code, data, err = self.run_cli("inventory", "note.md", *extra)
        self.assertEqual(err, "", err)
        return code, data

    def test_classifies_structure_modals_imperatives_and_code_as_obligations(self):
        code, data = self.inventory(INVENTORY_DOC)
        self.assertEqual(code, 0, data)
        entry = data["files"][0]
        texts = [item["text"] for item in entry["obligations"]]
        for expected in (
            "# Title", "Keep this fact.", "- a list item", "| a | b |", "| 1 | 2 |",
            "Use `x` here.", "Visit https://example.com/a for more.", "Nothing ends this line",
        ):
            self.assertIn(expected, texts)
        self.assertTrue(any(t.startswith("```") for t in texts))
        self.assertNotIn("|---|---|", texts)

    def test_history_sentence_is_a_leftover_and_repeats_are_one_class_plus_a_copy(self):
        code, data = self.inventory(INVENTORY_DOC)
        entry = data["files"][0]
        leftovers = [item["text"] for item in entry["leftovers"]]
        self.assertIn("The history of this note is long and motivational.", leftovers)
        self.assertEqual(leftovers.count("Repeated padding sentence here."), 1)
        self.assertEqual(entry["copies"], [{"text": "Repeated padding sentence here.", "count": 2}])

    def test_modal_sentence_is_an_obligation(self):
        code, data = self.inventory("# T\n\nThe tool must not write files.\n\nThe past was long.\n")
        entry = data["files"][0]
        self.assertIn("The tool must not write files.", [i["text"] for i in entry["obligations"]])
        self.assertEqual([i["text"] for i in entry["leftovers"]], ["The past was long."])

    def test_inventory_writes_nothing_and_ignores_stdin(self):
        path = self.repo / "note.md"
        path.write_text(INVENTORY_DOC)
        code, data, err = self.run_cli("inventory", "note.md", raw="not-json")
        self.assertEqual(code, 0, data)
        self.assertEqual(path.read_text(), INVENTORY_DOC)

    def test_cross_file_copy_is_reported_and_stays_in_its_class(self):
        sentence = "The shared padding line stays here."
        skill = SKILL.replace("The history of this skill is long motivational padding.", sentence)
        root = self.write_skill_set(skill, sentence + "\n")
        code, data, err = self.run_cli("inventory", "skills/engineering/demo")
        self.assertEqual(code, 0, data)
        by_path = {item["path"]: item for item in data["files"]}
        self.assertEqual(by_path["SKILL.md"]["cross_file_copies"], [{"text": sentence, "paths": ["notes.md"]}])
        self.assertIn(sentence, [i["text"] for i in by_path["notes.md"]["leftovers"]])
        self.assertEqual(by_path["SKILL.md"]["copies"], [])

    def test_failures_use_the_existing_names(self):
        (self.repo / "note.json").write_text("{}\n")
        code, data, err = self.run_cli("inventory", "note.json")
        self.assertEqual(data["failures"], ["unsupported_type"])
        folder = self.repo / "notes"
        folder.mkdir()
        code, data, err = self.run_cli("inventory", "notes")
        self.assertEqual(data["failures"], ["not_a_skill_directory"])


class WalkTests(Base):
    WALK = "# T\n\nKeep this fact.\n\nThe history here is long.\n\n- an item\n"

    def run_walk(self, candidate, command="check"):
        path = self.repo / "note.md"
        path.write_text(self.WALK)
        code, data, err = self.run_cli(command, "note.md", candidate=candidate)
        self.assertEqual(err, "", err)
        return code, data, path

    def test_leftover_deletion_passes(self):
        code, data, _ = self.run_walk({"note.md": "# T\n\nKeep this fact.\n\n- an item\n"})
        self.assertEqual(code, 0, data)
        self.assertEqual(data["defects"], [])

    def test_dropped_obligation_fails_and_names_sentence_and_stops_the_walk(self):
        code, data, path = self.run_walk({"note.md": "# T\n\nKeep this fact.\n"})
        self.assertEqual(data["failures"], ["obligation"])
        self.assertEqual(
            data["defects"], [{"rule": "obligation", "path": "note.md", "span": "- an item"}],
        )
        self.assertEqual(path.read_text(), self.WALK)

    def test_quote_with_present_sentence_passes_and_absent_sentence_fails(self):
        base = "# T\n\nKeep this fact.\n"
        code, data, _ = self.run_walk({"note.md": base, "quotes": {"- an item": "Keep this fact."}})
        self.assertEqual(code, 0, data)
        code, data, _ = self.run_walk({"note.md": base, "quotes": {"- an item": "Not in the file."}})
        self.assertEqual(data["failures"], ["obligation"])

    def test_quote_of_a_non_obligation_is_unknown_quote(self):
        code, data, _ = self.run_walk({
            "note.md": "# T\n\nKeep this fact.\n\n- an item\n",
            "quotes": {"The history here is long.": "Keep this fact."},
        })
        self.assertEqual(data["failures"], ["unknown_quote"])

    def test_quote_cannot_excuse_a_protected_span(self):
        original = "# T\n\n```\ncode\n```\n\nKeep this fact.\n\nThe history here is long.\n"
        (self.repo / "note.md").write_text(original)
        code, data, err = self.run_cli("check", "note.md", candidate={
            "note.md": "# T\n\nKeep this fact.\n",
            "quotes": {"``` code ```": "Keep this fact."},
        })
        self.assertEqual(data["failures"], ["protected_span"])

    def test_added_sentence_fails(self):
        code, data, _ = self.run_walk({"note.md": "# T\n\nKeep this fact.\n\nA fresh sentence appears.\n\n- an item\n"})
        self.assertEqual(data["failures"], ["added_sentence"])
        self.assertEqual(data["defects"][0]["span"], "A fresh sentence appears.")

    def test_one_not_clause_is_allowed_and_a_second_is_not(self):
        long_skill = SKILL.replace("description: Compress a demo skill.", "description: Compress a demo skill. Use it often.")
        root = self.write_skill_set(skill=long_skill)
        one = SKILL_SHORT.replace("Compress a demo skill.", "Compress a demo skill. Not a draft; that is terse.")
        code, data, err = self.run_cli("check", "demo", candidate={"SKILL.md": one})
        self.assertEqual(code, 0, data)
        two = SKILL_SHORT.replace("Compress a demo skill.", "Compress a demo skill. Not a draft. Also something new.")
        code, data, err = self.run_cli("check", "demo", candidate={"SKILL.md": two})
        self.assertEqual(data["failures"], ["added_sentence"])
        self.assertEqual(data["defects"][0]["span"], "Also something new.")

    def test_copies_that_remain_fail_exact_copy(self):
        original = "# T\n\nPadding sentence one.\n\nPadding sentence one.\n\nPadding sentence one.\n\nGone soon here.\n"
        (self.repo / "note.md").write_text(original)
        code, data, err = self.run_cli("check", "note.md", candidate={
            "note.md": "# T\n\nPadding sentence one.\n\nPadding sentence one.\n",
        })
        self.assertEqual(data["failures"], ["exact_copy"])
        code, data, err = self.run_cli("check", "note.md", candidate={
            "note.md": "# T\n\nPadding sentence one.\n",
        })
        self.assertEqual(code, 0, data)

    def test_deleting_the_last_obligation_copy_fails_obligation(self):
        original = "# T\n\n- same item\n\n- same item\n\nThe padding is long.\n"
        (self.repo / "note.md").write_text(original)
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": "# T\n"})
        self.assertEqual(data["failures"], ["obligation"])

    def test_only_the_first_failing_rule_is_reported_with_every_span(self):
        # drops two obligations and also breaks a later rule (word growth in a second file is not needed:
        # added_sentence follows obligation in the order)
        code, data, _ = self.run_walk({"note.md": "A fresh sentence appears.\n"})
        self.assertEqual(data["failures"], ["obligation"])
        self.assertEqual({d["rule"] for d in data["defects"]}, {"obligation"})
        self.assertGreaterEqual(len(data["defects"]), 3)

    def test_two_checks_return_equal_defects(self):
        _, first, _ = self.run_walk({"note.md": "# T\n"})
        _, second, _ = self.run_walk({"note.md": "# T\n"})
        self.assertEqual(first["defects"], second["defects"])

    def test_apply_writes_nothing_when_the_walk_fails(self):
        code, data, path = self.run_walk({"note.md": "# T\n"}, command="apply")
        self.assertNotEqual(code, 0)
        self.assertEqual(path.read_text(), self.WALK)

    def test_quotes_key_is_not_a_file(self):
        root = self.write_skill_set(notes="The note states one fact.\n\nThe history of this note is long and motivational.\n")
        code, data, err = self.run_cli("apply", "demo", candidate={
            "SKILL.md": SKILL_SHORT, "quotes": {},
        })
        self.assertEqual(code, 0, data)
        self.assertFalse((root / "quotes").exists())
        self.assertFalse((self.repo / "quotes").exists())


if __name__ == "__main__":
    unittest.main()
