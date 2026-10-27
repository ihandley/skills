import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import engine  # noqa: E402

NPM_DIFF = """\
diff --git a/package.json b/package.json
index 111..222 100644
--- a/package.json
+++ b/package.json
@@ -1,5 +1,5 @@
 {
   "dependencies": {
-    "lodash": "^4.17.20",
+    "lodash": "^4.17.21"
   }
}
diff --git a/src/app.ts b/src/app.ts
index 111..222 100644
--- a/src/app.ts
+++ b/src/app.ts
@@ -1 +1 @@
-export const x = 1
+export const x = 2
"""

GO_DIFF = """\
diff --git a/go.mod b/go.mod
--- a/go.mod
+++ b/go.mod
@@ -1,3 +1,3 @@
 module example.com/app
-require github.com/foo/bar v1.2.3
+require github.com/foo/bar v1.4.0
"""

ACTION_DIFF = """\
diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -1,3 +1,3 @@
 jobs:
   test:
-    uses: actions/checkout@v4
+    uses: actions/checkout@v5
"""

POM_DIFF = """\
diff --git a/pom.xml b/pom.xml
--- a/pom.xml
+++ b/pom.xml
@@ -1,4 +1,4 @@
     <artifactId>spring-core</artifactId>
-    <version>5.3.0</version>
+    <version>5.3.1</version>
"""

TEMPLATE = """\
## Objective

## Business Value / Impact

## Acceptance Criteria
"""


def verdict(**overrides):
    base = {
        "verdict": "Merge",
        "one_line_reason": "Patch with no breaking changes.",
        "breaks": [],
        "impact": [{"area": "App", "line": "imports the package"}],
    }
    base.update(overrides)
    return base


def packet():
    return {
        "pr": {"owner": "acme", "repo": "app", "number": 12, "url": "https://github.com/acme/app/pull/12", "title": "bump"},
        "packages": [{"ecosystem": "npm", "name": "lodash", "old": "4.17.20", "new": "4.17.21", "bump": "patch"}],
        "security": False,
        "changelog_missing": False,
        "changelog": "fixed a bug",
        "ci": {"state": "pass", "names": []},
        "usage": [],
    }


class ParseTests(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(engine.classify_bump("4.17.20", "4.17.21"), "patch")
        self.assertEqual(engine.classify_bump("^1.2.0", "1.3.0"), "minor")
        self.assertEqual(engine.classify_bump("v4", "v5"), "major")

    def test_npm_bump_and_mixed_diff(self):
        with self.assertRaises(engine.Stop) as caught:
            engine.parse_diff(NPM_DIFF)
        self.assertIn("mixed diff", caught.exception.message)
        self.assertIn("src/app.ts", caught.exception.message)

    def test_go_and_actions_and_pom(self):
        go = engine.parse_diff(GO_DIFF)
        self.assertEqual(go[0]["bump"], "minor")
        self.assertEqual(go[0]["name"], "github.com/foo/bar")
        action = engine.parse_diff(ACTION_DIFF)
        self.assertEqual(action[0]["name"], "actions/checkout")
        self.assertEqual(action[0]["bump"], "major")
        pom = engine.parse_diff(POM_DIFF)
        self.assertEqual(pom[0]["name"], "spring-core")
        self.assertEqual(pom[0]["bump"], "patch")

    def test_unknown_ecosystem(self):
        diff = "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-a\n+b\n"
        with self.assertRaises(engine.Stop) as caught:
            engine.parse_diff(diff)
        self.assertIn("unknown ecosystem", caught.exception.message)

    def test_repo_ref(self):
        pr = engine.parse_pr_ref("https://github.com/acme/app/pull/9")
        self.assertEqual(pr["number"], 9)
        self.assertTrue(engine.same_repo("acme/app", pr))
        self.assertFalse(engine.same_repo("other/app", pr))


class DecideTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        root = Path(self.root.name)
        (root / "src").mkdir()
        (root / "src" / "app.ts").write_text("import { debounce } from 'lodash'\n", encoding="utf-8")
        (root / "test").mkdir()
        (root / "test" / "app.test.ts").write_text("debounce()\n", encoding="utf-8")

    def build(self, verdict, outcomes, changelog_missing=False):
        body = packet()
        body["changelog_missing"] = changelog_missing
        return engine.build_state(body, verdict, self.root.name, outcomes)

    def test_symbol_hit_ignores_tests(self):
        state = self.build(verdict(breaks=[{"kind": "symbol", "name": "debounce"}]), {"no_change_status": "In Review", "code_change_status": "Ready for Dev", "code_change_flag": "Impediment"})
        self.assertTrue(state["code_change"])
        self.assertEqual(state["status_name"], "Ready for Dev")
        self.assertEqual(state["flag"], "Impediment")
        self.assertIn("src/app.ts", engine.grep_symbol(self.root.name, "debounce")[0])
        self.assertNotIn("test", engine.grep_symbol(self.root.name, "debounce")[0])

    def test_symbol_miss_does_not_flag(self):
        state = self.build(verdict(breaks=[{"kind": "symbol", "name": "missingSymbol"}]), {"no_change_status": "In Review", "code_change_status": "Ready for Dev"})
        self.assertFalse(state["code_change"])
        self.assertEqual(state["status_name"], "In Review")
        self.assertIsNone(state["flag"])

    def test_missing_changelog_and_hold(self):
        state = self.build(verdict(verdict="Verify"), {"code_change_status": "Ready for Dev"}, changelog_missing=True)
        self.assertTrue(state["code_change"])
        self.assertEqual(state["code_change_line"], "changelog not found")
        held = self.build(verdict(verdict="Hold", one_line_reason="Removed the client constructor."), {"code_change_status": "Ready for Dev"})
        self.assertEqual(held["breaks"][0]["summary"], "Removed the client constructor.")
        investigate = self.build(verdict(verdict="Investigate", one_line_reason="Needs a look."), {"no_change_status": "In Review"})
        self.assertFalse(investigate["code_change"])

    def test_summary_and_security_priority(self):
        state = self.build(verdict(), {"no_change_status": "In Review"})
        self.assertEqual(state["summary"], "deps | lodash 4.17.20→4.17.21 (PR #12)")
        body = packet()
        body["packages"].append({"ecosystem": "npm", "name": "react", "old": "18.0.0", "new": "18.1.0", "bump": "minor"})
        body["security"] = True
        state = engine.build_state(body, verdict(), self.root.name, {})
        self.assertEqual(state["summary"], "deps | lodash+… (PR #12)")
        self.assertEqual(state["priority"], "High")

    def test_description_keeps_acceptance_unique(self):
        state = self.build(verdict(breaks=[{"kind": "behavior", "summary": "default timeout changed"}]), {"code_change_status": "Ready for Dev"})
        text = engine.render_description(TEMPLATE, state)
        self.assertIn("## Acceptance Criteria", text)
        self.assertIn("The required code change is in the branch before merge.", text)
        objective = text.split("## Business Value / Impact")[0]
        self.assertNotIn("The required code change is in the branch before merge.", objective)

    def test_comment_leads_with_the_change_and_ci(self):
        body = packet()
        body["ci"] = {"state": "fail", "names": ["build"]}
        state = engine.build_state(body, verdict(breaks=[{"kind": "behavior", "summary": "default timeout changed"}]), self.root.name, {})
        line = engine.comment_line(state)
        self.assertTrue(line.startswith("default timeout changed"))
        self.assertIn("CI fail: build", line)
        comment = engine.render_comment(state)
        self.assertIn("<!-- dependabot-audit:v1 -->", comment)
        self.assertIn("**Verdict:** Merge", comment)

    def test_brief_skips_an_unchanged_marker(self):
        state = self.build(verdict(), {})
        first = engine.render_brief(state)
        self.assertTrue(first["post"])
        self.assertTrue(first["brief"].startswith("No code change."))
        again = engine.render_brief(state, first["brief"])
        self.assertFalse(again["post"])

    def test_outcomes_missing(self):
        state = self.build(verdict(), None)
        self.assertTrue(state["outcomes_missing"])
        self.assertIsNone(state["status_name"])

    def test_status_plan(self):
        state = self.build(verdict(breaks=[{"kind": "behavior", "summary": "rename"}]), {"code_change_status": "Ready for Dev", "code_change_flag": "Impediment"})
        plan = engine.status_plan(state, [{"id": "10", "to": {"name": "Ready for Dev"}}], [{"id": "customfield_1", "name": "Flagged"}])
        self.assertEqual(plan["transition"]["id"], "10")
        self.assertEqual(plan["flag"]["value"], [{"value": "Impediment"}])
        clear = self.build(verdict(), {"no_change_status": "In Review", "code_change_flag": "Impediment"})
        plan = engine.status_plan(clear, [{"id": "11", "to": {"name": "In Review"}}], [{"id": "customfield_1", "name": "Flagged"}])
        self.assertEqual(plan["flag"]["value"], [])
        with self.assertRaises(engine.Stop):
            engine.status_plan(state, [{"id": "10", "to": {"name": "Other"}}], [{"id": "customfield_1", "name": "Flagged"}])


class OutcomesFileTests(unittest.TestCase):
    def test_load_section(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "outcomes.toml"
            path.write_text('[jira]\nno_change_status = "In Review"\n', encoding="utf-8")
            self.assertEqual(engine.load_outcomes(path, "jira")["no_change_status"], "In Review")
            self.assertIsNone(engine.load_outcomes(path, "github"))


if __name__ == "__main__":
    unittest.main()
