#!/usr/bin/env python3
"""Promotion rules for this repo, read from the skills on disk.

    python3 scripts/promotion.py check [--root PATH]

Prints one line per broken rule and exits 1. Exits 0 and prints nothing else
when every rule holds. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BUCKETS = ("engineering", "productivity")
SECTIONS = ["What it does", "When to reach for it", "Common questions", "It's working if"]
INSTALL_BLOCKS = ("claude-code", "skills-sh-whole-set", "skills-sh-one-skill")
ENTRY = re.compile(r"^- \*\*\[([^\]]+)\]\(([^)]+)\)\*\*")
INSTALL_LINE = re.compile(r"^\s*(claude plugin |npx skills@latest add |/plugin )")


def promoted(root: Path) -> dict[str, list[str]]:
    out = {}
    for bucket in BUCKETS:
        base = root / "skills" / bucket
        out[bucket] = sorted(p.parent.name for p in base.glob("*/SKILL.md")) if base.is_dir() else []
    return out


def mode_of(skill_dir: Path) -> str:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    head = text.split("---")[1] if text.startswith("---") else ""
    return "user" if re.search(r"^disable-model-invocation:\s*true\s*$", head, re.M) else "model"


def yaml_mode(skill_dir: Path) -> str | None:
    path = skill_dir / "agents" / "openai.yaml"
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    return "user" if re.search(r"allow_implicit_invocation:\s*false", text) else "model"


def readme_groups(text: str, heading: str | None) -> dict[str, str]:
    """Map skill name to 'user' or 'model' for the entries under heading (None = whole file)."""
    lines = text.splitlines()
    if heading is not None:
        start = next((i for i, l in enumerate(lines) if l.strip() == heading), None)
        if start is None:
            return {}
        level = len(heading) - len(heading.lstrip("#"))
        end = len(lines)
        for i in range(start + 1, len(lines)):
            m = re.match(r"^(#+) ", lines[i])
            if m and len(m.group(1)) <= level:
                end = i
                break
        lines = lines[start + 1:end]
    groups, current = {}, None
    for line in lines:
        stripped = line.strip().strip("#").strip().strip("*").strip().lower()
        if stripped == "user-invoked":
            current = "user"
        elif stripped == "model-invoked":
            current = "model"
        else:
            m = ENTRY.match(line)
            if m and current:
                groups[m.group(1)] = current
    return groups


def canonical_blocks(root: Path) -> dict[str, list[str]]:
    text = (root / ".agents" / "install-block.md").read_text(encoding="utf-8")
    blocks = {}
    for name, body in re.findall(r'<canonical-block name="([^"]+)">(.*?)</canonical-block>', text, re.S):
        blocks[name] = [l.strip() for fence in re.findall(r"```\w*\n(.*?)```", body, re.S)
                        for l in fence.splitlines() if l.strip()]
    return blocks


def canonical_line_ok(line: str, allowed: set[str]) -> bool:
    if line in allowed:
        return True
    pattern = [re.escape(a).replace(re.escape("<name>"), r"[a-z0-9-]+") for a in allowed if "<name>" in a]
    return any(re.fullmatch(p, line) for p in pattern)


def check(root: Path) -> list[str]:
    problems = []
    groups = promoted(root)
    folders = {b: set(names) for b, names in groups.items()}
    all_names = {n for names in folders.values() for n in names}

    manifest = json.loads((root / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    listed = set(manifest.get("skills", []))
    want = {"./skills/%s/%s" % (b, n) for b, names in folders.items() for n in names}
    for path in sorted(want - listed):
        problems.append("plugin.json: missing %s" % path)
    for path in sorted(listed - want):
        problems.append("plugin.json: lists %s, which is not a promoted skill folder" % path)

    modes = {}
    for bucket, names in folders.items():
        for name in sorted(names):
            skill_dir = root / "skills" / bucket / name
            modes[(bucket, name)] = mode_of(skill_dir)
            agent = yaml_mode(skill_dir)
            if agent is None:
                problems.append("%s/%s: agents/openai.yaml is missing" % (bucket, name))
            elif agent != modes[(bucket, name)]:
                problems.append("%s/%s: SKILL.md says %s-invoked, agents/openai.yaml says %s-invoked"
                                % (bucket, name, modes[(bucket, name)], agent))

    top = (root / "README.md").read_text(encoding="utf-8")
    for bucket in BUCKETS:
        for source, found in (
            ("README.md", readme_groups(top, "### " + bucket.capitalize())),
            ("skills/%s/README.md" % bucket,
             readme_groups((root / "skills" / bucket / "README.md").read_text(encoding="utf-8"), None)),
        ):
            for name in sorted(folders[bucket]):
                want_mode = modes[(bucket, name)]
                if name not in found:
                    problems.append("%s: %s is not listed" % (source, name))
                elif found[name] != want_mode:
                    problems.append("%s: %s is under %s-invoked, its mode is %s-invoked"
                                    % (source, name, found[name], want_mode))
            for name in sorted(set(found) - folders[bucket]):
                problems.append("%s: lists %s, which is not a promoted %s skill" % (source, name, bucket))

    for bucket in BUCKETS:
        docs = root / "docs" / bucket
        pages = {p.stem: p for p in docs.glob("*.md")} if docs.is_dir() else {}
        for name in sorted(folders[bucket]):
            if name not in pages:
                problems.append("docs/%s/%s.md: missing" % (bucket, name))
        for name, page in sorted(pages.items()):
            text = page.read_text(encoding="utf-8")
            headings = [l[3:].strip() for l in text.splitlines() if l.startswith("## ")]
            if headings != SECTIONS:
                problems.append("docs/%s/%s.md: sections are %s, expected %s" % (bucket, name, headings, SECTIONS))
            if name not in all_names and not text.lstrip().startswith("> **Archived.**"):
                problems.append("docs/%s/%s.md: no promoted skill by this name, and the page is not marked archived"
                                % (bucket, name))

    removed = root / ".agents" / "removed-skills.txt"
    for entry in removed.read_text(encoding="utf-8").splitlines() if removed.is_file() else []:
        entry = entry.strip()
        if not entry or entry.startswith("#"):
            continue
        bucket, _, name = entry.partition("/")
        page = root / "docs" / bucket / ("%s.md" % name)
        if not page.is_file():
            problems.append("docs/%s/%s.md: removed skill has no archived page" % (bucket, name))
        elif not page.read_text(encoding="utf-8").lstrip().startswith("> **Archived.**"):
            problems.append("docs/%s/%s.md: removed skill's page is not marked archived" % (bucket, name))

    blocks = canonical_blocks(root)
    for name in INSTALL_BLOCKS:
        if not blocks.get(name):
            problems.append(".agents/install-block.md: canonical block %r is missing" % name)
    allowed = {l for ls in blocks.values() for l in ls}
    readme_lines = {l.strip() for l in top.splitlines()}
    for name in ("claude-code", "skills-sh-whole-set"):
        for line in blocks.get(name, []):
            if line not in readme_lines:
                problems.append("README.md: install command drifted from the canonical block %r: %s" % (name, line))
    files = [root / "README.md", *(root / "docs").rglob("*.md"), *(root / "skills").glob("*/README.md"),
             *(root / "skills").glob("*/*/README.md")]
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if INSTALL_LINE.match(line) and not canonical_line_ok(line.strip(), allowed):
                problems.append("%s: install command is not in the canonical block: %s"
                                % (path.relative_to(root), line.strip()))
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="promotion.py")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args(argv)
    problems = check(Path(args.root))
    for line in problems:
        print(line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
