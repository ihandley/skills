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
NOTES_GROWN = "The note states one fact and then adds several more words.\n"


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

    def test_broken_relative_link_is_rejected(self):
        path = self.repo / "note.md"
        original = "# Title\n\nSee [the note](other.md).\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        (self.repo / "other.md").write_text("One fact.\n")
        candidate = "# Title\n\nSee [the note](missing.md).\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["link"])
        self.assertEqual(path.read_text(), original)
        self.assertEqual((self.repo / "other.md").read_text(), "One fact.\n")

    def test_broken_heading_anchor_is_rejected(self):
        path = self.repo / "note.md"
        original = "# Keep This\n\nSee [the section](#keep-this).\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "# Kept\n\nSee [the section](#keep-this).\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["heading_anchor"])
        self.assertEqual(path.read_text(), original)

    def test_unresolved_reference_is_listed_and_left_out(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        text = (
            "---\nname: demo\ndescription: Demo skill.\n---\n\n# Demo\n\n"
            "Read [the notes](notes.md). The shape lives in `templates/<issue-type>.md`.\n\n"
            "The history of this skill is long motivational padding.\n\nKeep the signal.\n"
        )
        short = text.replace("The history of this skill is long motivational padding.\n\n", "")
        (root / "SKILL.md").write_text(text)
        (root / "notes.md").write_text("One fact.\n")
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
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL)
        (root / "notes.md").write_text(NOTES)
        code, data, err = self.run_cli(
            "check", "skills/engineering/demo", candidate={"SKILL.md": SKILL_SHORT},
        )
        self.assertEqual(err, "", err)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["failures"], [])
        # Description value "Compress a demo skill." is outside the gate: 34 tokens - 4 = 30, then the 9-word history sentence is gone.
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
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL)
        (root / "notes.md").write_text(NOTES)
        code, data, err = self.run_cli(
            "apply", "skills/engineering/demo",
            candidate={"SKILL.md": SKILL_SHORT, "notes.md": NOTES_GROWN},
        )
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["word_growth"])
        self.assertEqual(data["words_before"], 35)
        self.assertEqual(data["words_after"], 32)
        self.assertEqual((root / "SKILL.md").read_text(), SKILL)
        self.assertEqual((root / "notes.md").read_text(), NOTES)

    def test_apply_writes_every_replaced_file_or_none(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL)
        (root / "notes.md").write_text(NOTES)
        notes_short = "One fact.\n"
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
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL)
        (root / "notes.md").write_text(NOTES)
        described = SKILL.replace("description: Compress a demo skill.", "description: Compress a skill.")
        code, data, err = self.run_cli("check", "skills/engineering/demo", candidate={"SKILL.md": described})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["word_total"])
        self.assertEqual(data["words_before"], 35)
        self.assertEqual(data["words_after"], 35)
        self.assertEqual(data["description_chars_before"], 22)
        self.assertEqual(data["description_chars_after"], 17)
        self.assertEqual((root / "SKILL.md").read_text(), SKILL)

    def test_description_over_1024_characters_is_rejected(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        text = (
            "---\nname: demo\ndescription: Demo skill.\n---\n\n"
            "Keep the signal.\n\nThe history of this skill is long motivational padding.\n"
        )
        described = text.replace("description: Demo skill.", "description: " + ("x" * 1025))
        described = described.replace("The history of this skill is long motivational padding.\n", "")
        (root / "SKILL.md").write_text(text)
        code, data, err = self.run_cli("check", "skills/engineering/demo", candidate={"SKILL.md": described})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["description_cap"])
        self.assertEqual(data["description_chars_after"], 1025)
        self.assertEqual(data["description_cap"], 1024)
        self.assertEqual((root / "SKILL.md").read_text(), text)

    def test_unlinked_readme_stays_out_of_the_set(self):
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL)
        (root / "notes.md").write_text(NOTES)
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
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL)
        (root / "notes.md").write_text(NOTES)
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
        root = self.repo / "skills" / "engineering" / "demo"
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(SKILL)
        (root / "notes.md").write_text(NOTES)
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

    def test_nested_frontmatter_fails_parse(self):
        path = self.repo / "note.md"
        original = "---\ntitle: Note\n---\n\nKeep this fact.\n\nThe history of this note is long and motivational.\n"
        path.write_text(original)
        candidate = "---\nmetadata:\n  author: ada\n---\n\nKeep this fact.\n"
        code, data, err = self.run_cli("check", "note.md", candidate={"note.md": candidate})
        self.assertEqual(err, "", err)
        self.assertNotEqual(code, 0)
        self.assertEqual(data["failures"], ["parse"])
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


if __name__ == "__main__":
    unittest.main()
