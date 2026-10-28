#!/usr/bin/env python3
"""Selection rules over in-memory lists. No files, no CLI."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import selection  # noqa: E402


def item(item_id, order, status="pending", parent=None, depends=()):
    return {"id": item_id, "order": order, "status": status, "parent_id": parent,
            "depends_on": list(depends)}


def ctx(*items):
    return {"items": list(items)}


def status(c, item_id):
    return selection.find(c, item_id)["status"]


class FlatListTests(unittest.TestCase):
    def test_first_pending_by_order_is_chosen(self):
        c = ctx(item("a", 0, "verified"), item("c", 2), item("b", 1))
        self.assertEqual(selection.choose_next(c)["id"], "b")

    def test_after_finishing_an_item_the_next_pending_is_chosen(self):
        c = ctx(item("a", 0, "verified"), item("b", 1), item("c", 2))
        self.assertEqual(selection.choose_next(c, selection.find(c, "a"))["id"], "b")

    def test_nothing_pending_chooses_nothing(self):
        c = ctx(item("a", 0, "verified"), item("b", 1, "blocked"), item("c", 2, "deferred"))
        self.assertIsNone(selection.choose_next(c))

    def test_activate_next_marks_only_the_chosen_item(self):
        c = ctx(item("a", 0), item("b", 1))
        selection.activate_next(c)
        self.assertEqual((status(c, "a"), status(c, "b")), ("active", "pending"))


class TreeTests(unittest.TestCase):
    def tree(self):
        return ctx(
            item("p", 0, "pending"),
            item("p1", 0, "pending", parent="p"),
            item("p2", 1, "pending", parent="p"),
            item("q", 1, "pending"),
        )

    def test_a_parent_with_unfinished_children_is_skipped_for_its_first_leaf(self):
        self.assertEqual(selection.choose_next(self.tree())["id"], "p1")

    def test_after_the_last_child_the_parent_becomes_next(self):
        c = self.tree()
        for leaf in ("p1", "p2"):
            selection.find(c, leaf)["status"] = "verified"
        self.assertEqual(selection.choose_next(c, selection.find(c, "p2"))["id"], "p")

    def test_after_a_child_the_next_sibling_is_chosen(self):
        c = self.tree()
        selection.find(c, "p1")["status"] = "verified"
        self.assertEqual(selection.choose_next(c, selection.find(c, "p1"))["id"], "p2")

    def test_after_a_finished_parent_the_next_top_level_is_chosen(self):
        c = self.tree()
        for done in ("p", "p1", "p2"):
            selection.find(c, done)["status"] = "verified"
        self.assertEqual(selection.choose_next(c, selection.find(c, "p"))["id"], "q")

    def test_a_flat_list_and_the_same_list_as_a_tree_agree(self):
        flat = ctx(item("a", 0, "verified"), item("b", 1), item("c", 2))
        self.assertEqual(selection.choose_next(flat, selection.find(flat, "a"))["id"], "b")


class DependencyHelperTests(unittest.TestCase):
    def test_unmet_lists_unresolved_and_missing_dependencies(self):
        c = ctx(item("a", 0, "pending"), item("b", 1, "pending", depends=["a", "ghost"]))
        self.assertEqual(selection.unmet(c, selection.find(c, "b")), ["a", "ghost"])

    def test_cancelled_counts_as_resolved(self):
        c = ctx(item("a", 0, "cancelled"), item("b", 1, "pending", depends=["a"]))
        self.assertEqual(selection.unmet(c, selection.find(c, "b")), [])


class SkipTargetTests(unittest.TestCase):
    def test_skip_refuses_when_the_next_item_depends_on_the_held_one(self):
        c = ctx(item("a", 0, "active"), item("b", 1, depends=["a"]))
        target, reason = selection.skip_target(c, selection.find(c, "a"))
        self.assertIsNone(target)
        self.assertIn("depends on a", reason)

    def test_skip_moves_to_an_independent_later_item(self):
        c = ctx(item("a", 0, "active"), item("b", 1))
        target, reason = selection.skip_target(c, selection.find(c, "a"))
        self.assertEqual((target["id"], reason), ("b", None))

    def test_skip_with_no_later_item(self):
        c = ctx(item("a", 0, "active"))
        self.assertEqual(selection.skip_target(c, selection.find(c, "a")), (None, "no later item"))


class DependencyRuleTests(unittest.TestCase):
    def test_a_successor_of_a_blocked_item_is_not_chosen(self):
        c = ctx(item("a", 0, "blocked"), item("b", 1, depends=["a"]), item("c", 2, depends=["b"]))
        self.assertIsNone(selection.choose_next(c))

    def test_activate_next_leaves_that_successor_pending(self):
        c = ctx(item("a", 0, "blocked"), item("b", 1, depends=["a"]))
        selection.activate_next(c)
        self.assertEqual(status(c, "b"), "pending")

    def test_an_independent_item_is_still_chosen_past_a_blocked_one(self):
        c = ctx(item("a", 0, "blocked"), item("b", 1, depends=["a"]), item("c", 2))
        self.assertEqual(selection.choose_next(c)["id"], "c")

    def test_skip_and_choose_agree_for_that_list(self):
        c = ctx(item("a", 0, "blocked"), item("b", 1, depends=["a"]))
        held = selection.find(c, "a")
        self.assertIsNone(selection.skip_target(c, held)[0])
        self.assertIsNone(selection.choose_next(c))

    def test_a_tree_refuses_a_leaf_with_an_unmet_dependency(self):
        c = ctx(
            item("p", 0, "pending"),
            item("p1", 0, "blocked", parent="p"),
            item("p2", 1, "pending", parent="p", depends=["p1"]),
        )
        self.assertIsNone(selection.choose_next(c))

    def test_a_tree_parent_with_an_unmet_dependency_is_not_chosen(self):
        c = ctx(item("a", 0, "blocked"), item("p", 1, "pending", depends=["a"]),
                item("p1", 0, "pending", parent="p"))
        self.assertIsNone(selection.choose_next(c))


if __name__ == "__main__":
    unittest.main()
