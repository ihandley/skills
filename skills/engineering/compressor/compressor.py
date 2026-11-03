#!/usr/bin/env python3
"""Check a candidate against one document, and apply it when every check passes.

The script is the only writer. It does not commit.
"""

from __future__ import annotations

import difflib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

FAILURE_ORDER = [
    "not_utf8",
    "unsupported_type",
    "wrong_arity",
    "bad_command",
    "bad_json",
    "skill_not_found",
    "ambiguous_skill",
    "not_a_skill_directory",
    "escaping_key",
    "unknown_key",
    "parse",
    "frontmatter_keys",
    "frontmatter_value",
    "protected_span",
    "link",
    "heading_anchor",
    "word_total",
    "word_growth",
    "description_cap",
]
TEXT_SUFFIXES = {".md", ".txt"}
LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
URL_RE = re.compile(r"https?://[^\s<>)\]]+")
BARE_PATH_RE = re.compile(
    r"(?<![\w./])((?:\./|\.\./)?(?:[A-Za-z0-9_.<>-]+/)*[A-Za-z0-9_.<>-]+\.[A-Za-z0-9]+)"
)
BARE_DIR_RE = re.compile(r"(?<![\w./])((?:\./|\.\./)?(?:[A-Za-z0-9_.<>-]+/)+)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(.*)$")
BLOCK_RE = re.compile(r"^([|>])([+-])?([0-9]+)?$")
NESTED_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:")


class Located:
    def __init__(self, kind: str, root: Path, members: list[str], skipped: list[str], unresolved: list[str]):
        self.kind = kind
        self.root = root
        self.members = members
        self.skipped = skipped
        self.unresolved = unresolved


class Matter:
    def __init__(self):
        self.ok = True
        self.keys: list[str] = []
        self.values: dict[str, str] = {}
        self.spans: dict[str, tuple[int, int]] = {}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 2:
        emit(empty_report(["wrong_arity"]))
        return 1
    command, arg = argv
    if command not in ("check", "apply"):
        emit(empty_report(["bad_command"]))
        return 1
    candidate, failure = load_candidate()
    if failure:
        emit(empty_report([failure]))
        return 1

    located = locate(arg, Path.cwd())
    if isinstance(located, str):
        emit(empty_report([located]))
        return 1
    report, replacements = evaluate(located, candidate)
    if command == "apply" and report["ok"]:
        replace_staged_files(replacements)
    emit(report)
    return 0 if report["ok"] else 1


def load_candidate() -> tuple[dict | None, str | None]:
    raw = sys.stdin.buffer.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "not_utf8"
    try:
        value = json.loads(text) if text.strip() else None
    except json.JSONDecodeError:
        return None, "bad_json"
    if not isinstance(value, dict) or any(not isinstance(item, str) for item in value.values()):
        return None, "bad_json"
    return value, None


def locate(arg: str, cwd: Path) -> Located | str:
    path = Path(arg)
    if not path.is_absolute():
        path = cwd / path
    if path.is_dir():
        if not (path / "SKILL.md").is_file():
            return "not_a_skill_directory"
        return load_skill(path)
    if path.is_file():
        if path.name == "SKILL.md":
            return load_skill(path.parent)
        return Located("document", path.parent, [path.name], [], [])
    return resolve_name(arg, cwd)


def resolve_name(name: str, cwd: Path) -> Located | str:
    skills_dir = find_skills(cwd)
    if skills_dir is None:
        return "skill_not_found"
    matches = sorted(skills_dir.glob("*/" + name + "/SKILL.md"))
    if not matches:
        return "skill_not_found"
    if len(matches) > 1:
        return "ambiguous_skill"
    return load_skill(matches[0].parent)


def find_skills(cwd: Path) -> Path | None:
    for parent in [cwd, *cwd.parents]:
        if parent.name == "skills" and parent.is_dir():
            return parent
        nested = parent / "skills"
        if nested.is_dir():
            return nested
    return None


def load_skill(root: Path) -> Located:
    try:
        text = (root / "SKILL.md").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    members = ["SKILL.md"]
    skipped: list[str] = []
    unresolved: list[str] = []
    seen: set[str] = set()
    for ref in relative_refs(text):
        if ref in seen:
            continue
        seen.add(ref)
        add_ref(root, ref, members, skipped, unresolved)
    return Located("skill", root, members, skipped, unresolved)


def relative_refs(text: str) -> list[str]:
    refs = []
    for line in outside_fences(text):
        for match in LINK_RE.finditer(line):
            dest = clean_dest(match.group(1))
            if is_relative(dest):
                refs.append(path_only(dest))
        refs.extend(literal_path_refs(line))
    return refs


def literal_path_refs(line: str) -> list[str]:
    refs = []
    masked = line
    for span in inline_codes_in(line):
        content = unwrap_code(span)
        if looks_like_rel(content):
            refs.append(content)
        masked = masked.replace(span, " " * len(span), 1)
    for match in BARE_PATH_RE.finditer(masked):
        token = match.group(1)
        if looks_like_rel(token):
            refs.append(token)
    for match in BARE_DIR_RE.finditer(masked):
        token = match.group(1)
        if looks_like_rel(token):
            refs.append(token)
    return refs


def unwrap_code(span: str) -> str:
    width = 0
    while width < len(span) and span[width] == "`":
        width += 1
    return span[width:-width].strip()


def looks_like_rel(token: str) -> bool:
    if not token or token.startswith(("/", "#")):
        return False
    lowered = token.lower()
    if lowered.startswith(("http://", "https://", "mailto:")):
        return False
    if not (BARE_PATH_RE.fullmatch(token) or BARE_DIR_RE.fullmatch(token)):
        return False
    return ".." not in Path(token).parts


def outside_fences(text: str) -> list[str]:
    lines = text.splitlines()
    hidden = fence_line_indexes(walk_fences(lines))
    return [line for index, line in enumerate(lines) if index not in hidden]


def clean_dest(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return raw[1:raw.index(">")].strip()
    return raw.split()[0] if raw else ""


def path_only(dest: str) -> str:
    return dest.split("#", 1)[0].split("?", 1)[0]


def is_relative(dest: str) -> bool:
    if not dest or dest.startswith("#"):
        return False
    lowered = dest.lower()
    if lowered.startswith(("http://", "https://", "mailto:")):
        return False
    return not dest.startswith("/")


def add_ref(root: Path, ref: str, members: list[str], skipped: list[str], unresolved: list[str]) -> None:
    target = contained(root, ref)
    if target is None:
        unresolved.append(ref)
        return
    if target.is_dir():
        for file in sorted(item for item in target.rglob("*") if item.is_file()):
            if file.suffix.lower() in TEXT_SUFFIXES:
                rel = file.resolve().relative_to(root.resolve()).as_posix()
                if rel not in members:
                    members.append(rel)
        return
    if target.is_file():
        rel = target.resolve().relative_to(root.resolve()).as_posix()
        if target.suffix.lower() in TEXT_SUFFIXES:
            if rel not in members:
                members.append(rel)
        elif rel not in skipped:
            skipped.append(rel)
        return
    unresolved.append(ref)


def escapes(key: str) -> bool:
    if key.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:[\\/]", key):
        return True
    return ".." in Path(key.replace("\\", "/")).parts


def contained(root: Path, ref: str) -> Path | None:
    path = Path(ref)
    if path.is_absolute() or ".." in path.parts:
        return None
    candidate = root.joinpath(*path.parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return candidate


def evaluate(loc: Located, candidate: dict) -> tuple[dict, list[tuple[Path, str]]]:
    if loc.kind == "document" and Path(loc.members[0]).suffix.lower() not in TEXT_SUFFIXES:
        return empty_report(["unsupported_type"]), []
    failures: list[str] = []
    for key in candidate:
        if escapes(key):
            failures.append("escaping_key")
        elif key not in loc.members:
            failures.append("unknown_key")
    files = []
    diffs = {}
    replacements = []
    words_before = 0
    words_after = 0
    entry_before = None
    entry_after = None
    originals: dict[str, str] = {}
    proposeds: dict[str, str] = {}
    for rel in loc.members:
        try:
            originals[rel] = (loc.root / rel).read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            failures.append("not_utf8")
        else:
            proposeds[rel] = candidate.get(rel, originals[rel])
    for rel in loc.members:
        if rel not in originals:
            continue
        path = loc.root / rel
        original = originals[rel]
        proposed = proposeds[rel]
        exclude_description_from_word_count = loc.kind == "skill" and rel == "SKILL.md"
        before = gated_words(original, exclude_description_from_word_count)
        after = gated_words(proposed, exclude_description_from_word_count)
        words_before += before
        words_after += after
        changed = proposed != original
        if changed and after > before:
            failures.append("word_growth")
        if protected_sequences(original) != protected_sequences(proposed):
            failures.append("protected_span")
        if rel.lower().endswith(".md"):
            if unclosed_fence(original) or unclosed_fence(proposed):
                failures.append("parse")
            failures.extend(frontmatter_failures(original, proposed, exclude_description_from_word_count))
            if broken_links(loc.root, rel, proposed, set(loc.members)) - broken_links(
                loc.root, rel, original, set(loc.members)
            ):
                failures.append("link")
            if broken_anchors(proposed, loc.root, rel, proposeds) - broken_anchors(original, loc.root, rel, originals):
                failures.append("heading_anchor")
        files.append({
            "path": rel,
            "disposition": "replaced" if changed else "unchanged",
            "words_before": before,
            "words_after": after,
        })
        if changed:
            diffs[rel] = unified(rel, original, proposed)
            replacements.append((path, proposed))
        if exclude_description_from_word_count:
            entry_before = description_len(original)
            entry_after = description_len(proposed)
    for rel in loc.skipped:
        files.append({
            "path": rel,
            "disposition": "skipped",
            "words_before": 0,
            "words_after": 0,
        })
    if loc.kind == "skill" and entry_after is not None and entry_after > 1024:
        failures.append("description_cap")
    if "not_utf8" not in failures and words_after >= words_before:
        failures.append("word_total")
    report = empty_report(ordered(failures))
    report["words_before"] = words_before
    report["words_after"] = words_after
    report["files"] = files
    report["skipped"] = list(loc.skipped)
    report["unresolved"] = list(loc.unresolved)
    report["diffs"] = diffs
    if loc.kind == "skill":
        report["description_chars_before"] = entry_before if entry_before is not None else 0
        report["description_chars_after"] = entry_after if entry_after is not None else 0
        report["description_cap"] = 1024
        report["sibling_median"] = sibling_median(loc.root)
    return report, replacements


def broken_anchors(text: str, root: Path | None = None, source_rel: str | None = None, texts: dict[str, str] | None = None) -> set[str]:
    slugs = heading_slugs(text)
    broken = set()
    for anchor in same_document_anchors(text):
        if anchor not in slugs:
            broken.add(anchor)
    if root is None or source_rel is None:
        return broken
    for file_part, fragment in cross_file_fragments(text):
        target = markdown_target(root, source_rel, file_part, texts or {})
        if target is None:
            continue
        if fragment not in heading_slugs(target):
            broken.add(file_part + "#" + fragment)
    return broken


def cross_file_fragments(text: str) -> list[tuple[str, str]]:
    found = []
    for line in outside_fences(text):
        for match in LINK_RE.finditer(line):
            dest = clean_dest(match.group(1))
            if not is_relative(dest) or "#" not in dest:
                continue
            file_part, fragment = dest.split("#", 1)
            file_part = path_only(file_part)
            fragment = fragment.split("?", 1)[0]
            if file_part and fragment:
                found.append((file_part, fragment))
    return found


def markdown_target(root: Path, source_rel: str, ref: str, texts: dict[str, str]) -> str | None:
    path = Path(ref)
    if path.is_absolute():
        return None
    base = (root / source_rel).parent
    candidate = base.joinpath(*path.parts) if path.parts else base
    try:
        relative = candidate.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        relative = None
    if relative and relative.lower().endswith(".md") and relative in texts:
        return texts[relative]
    if candidate.suffix.lower() != ".md" or not candidate.is_file():
        return None
    try:
        return candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def heading_slugs(text: str) -> set[str]:
    slugs = set()
    seen: dict[str, int] = {}
    for line in outside_fences(text):
        matched = HEADING_RE.match(line.strip())
        if not matched:
            continue
        base = github_slug(matched.group(1))
        count = seen.get(base, 0)
        seen[base] = count + 1
        slugs.add(base if count == 0 else "%s-%d" % (base, count))
    return slugs


def github_slug(heading: str) -> str:
    kept = []
    for char in heading.strip().lower():
        if char.isalnum() or char in " -":
            kept.append(char)
    slug = re.sub(r"\s+", "-", "".join(kept))
    return re.sub(r"-{2,}", "-", slug)


def same_document_anchors(text: str) -> list[str]:
    anchors = []
    for line in outside_fences(text):
        for match in LINK_RE.finditer(line):
            dest = clean_dest(match.group(1))
            if dest.startswith("#") and path_only(dest) == "":
                anchors.append(dest[1:])
    return anchors


def broken_links(root: Path, source_rel: str, text: str, members: set[str]) -> set[str]:
    broken = set()
    for ref in relative_file_links(text):
        if not link_resolves(root, source_rel, ref, members):
            broken.add(ref)
    return broken


def relative_file_links(text: str) -> list[str]:
    links = []
    for line in outside_fences(text):
        for match in LINK_RE.finditer(line):
            dest = clean_dest(match.group(1))
            if not is_relative(dest):
                continue
            file_part = path_only(dest)
            if file_part:
                links.append(file_part)
    return links


def link_resolves(root: Path, source_rel: str, ref: str, members: set[str]) -> bool:
    path = Path(ref)
    if path.is_absolute():
        return False
    base = (root / source_rel).parent
    candidate = base.joinpath(*path.parts) if path.parts else base
    try:
        relative = candidate.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return candidate.exists()
    if relative in members:
        return True
    return candidate.exists()


def frontmatter_failures(original: str, proposed: str, skill_entry: bool) -> list[str]:
    before = parse_frontmatter(original)
    after = parse_frontmatter(proposed)
    opened = original.startswith("---\n") or proposed.startswith("---\n")
    if opened and (not before.ok or not after.ok):
        return ["parse"]
    failures = []
    if before.keys != after.keys:
        failures.append("frontmatter_keys")
    keys = [key for key in before.keys if key in after.values]
    if skill_entry:
        keys = [key for key in keys if key != "description"]
    if any(before.values[key] != after.values[key] for key in keys):
        failures.append("frontmatter_value")
    return failures


def description_len(text: str) -> int:
    matter = parse_frontmatter(text)
    if not matter.ok:
        return 0
    return len(matter.values.get("description", ""))


def sibling_median(root: Path):
    lengths = []
    for skill in sorted(root.parent.glob("*/SKILL.md")):
        if skill.parent.resolve() == root.resolve():
            continue
        try:
            text = skill.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        matter = parse_frontmatter(text)
        if matter.ok:
            lengths.append(len(matter.values.get("description", "")))
    return median(lengths)


def median(values: list[int]):
    if not values:
        return None
    ordered_values = sorted(values)
    count = len(ordered_values)
    if count % 2:
        return ordered_values[count // 2]
    mean = (ordered_values[count // 2 - 1] + ordered_values[count // 2]) / 2
    return int(mean) if mean == int(mean) else mean


def gated_words(text: str, exclude_description_from_word_count: bool = False) -> int:
    if exclude_description_from_word_count:
        matter = parse_frontmatter(text)
        if matter.ok and "description" in matter.spans:
            start, end = matter.spans["description"]
            text = text[:start] + " " + text[end:]
    return len(strip_fences(text).split())


def parse_frontmatter(text: str) -> Matter:
    matter = Matter()
    if not text.startswith("---\n"):
        return matter
    lines = text.splitlines(keepends=True)
    offsets = []
    cursor = 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line)
    close = next((index for index in range(1, len(lines)) if lines[index].strip() == "---"), None)
    if close is None:
        matter.ok = False
        return matter
    index = 1
    while index < close:
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line[0] in " \t" or line.lstrip().startswith("#"):
            matter.ok = False
            return matter
        matched = KEY_RE.match(line.rstrip("\r\n"))
        if not matched:
            matter.ok = False
            return matter
        key, rest = matched.group(1), matched.group(2)
        if key in matter.values:
            matter.ok = False
            return matter
        value_text = rest[1:] if rest.startswith(" ") else rest
        indicator = value_text.strip()
        block = BLOCK_RE.fullmatch(indicator)
        if block and block.group(3):
            matter.ok = False
            return matter
        if block:
            content, next_index = read_block(lines, index + 1, close)
            matter.keys.append(key)
            matter.values[key] = render_block(content, block.group(1), block.group(2) or "")
            matter.spans[key] = (offsets[index + 1], offsets[next_index] if next_index < len(offsets) else offsets[close])
            index = next_index
            continue
        decoded = decode_scalar(indicator) if indicator else ""
        if indicator and decoded is None:
            matter.ok = False
            return matter
        if index + 1 < close and lines[index + 1][:1] in " \t" and lines[index + 1].strip():
            if indicator == "" and line_kind(lines[index + 1]) == "collection":
                node, next_index = parse_collection(lines, index + 1, close, 0)
                if node is None:
                    matter.ok = False
                    return matter
                decoded = json.dumps(node, ensure_ascii=False, separators=(",", ":"))
            else:
                continued, next_index = read_plain_lines(lines, index + 1, close, decoded)
                if continued is None:
                    matter.ok = False
                    return matter
                decoded = continued
            end = offsets[next_index] if next_index < len(offsets) else offsets[close]
        else:
            next_index = index + 1
            end = offsets[index] + len(line.rstrip("\r\n"))
        colon = line.index(":")
        start = offsets[index] + colon + 1
        if rest.startswith(" "):
            start += 1
        if indicator == "" and next_index == index + 1:
            start = end
        matter.keys.append(key)
        matter.values[key] = decoded
        matter.spans[key] = (start, end)
        index = next_index
    return matter


def read_block(lines: list[str], start: int, close: int) -> tuple[list[str], int]:
    index = start
    indent = None
    content = []
    while index < close:
        raw = lines[index].rstrip("\r\n")
        if raw.strip() == "":
            content.append("")
            index += 1
            continue
        current = len(raw) - len(raw.lstrip(" "))
        if indent is None:
            if current == 0:
                break
            indent = current
        if current < indent:
            break
        content.append(raw[indent:])
        index += 1
    return content, index


def render_block(lines: list[str], style: str, chomp: str) -> str:
    body = list(lines)
    trailing = 0
    while body and body[-1] == "":
        body.pop()
        trailing += 1
    core = fold_lines(body) if style == ">" else "\n".join(body)
    if not body:
        return "\n" * trailing if chomp == "+" else ""
    if chomp == "-":
        return core
    if chomp == "+":
        return core + ("\n" * (1 + trailing))
    return core + "\n"


def fold_lines(lines: list[str]) -> str:
    parts = []
    index = 0
    while index < len(lines):
        if lines[index] == "":
            blanks = 0
            while index < len(lines) and lines[index] == "":
                blanks += 1
                index += 1
            parts.append("\n" * blanks)
            continue
        piece = lines[index]
        index += 1
        while index < len(lines) and lines[index] != "":
            nxt = lines[index]
            piece += ("\n" if nxt[:1] in " \t" else " ") + nxt
            index += 1
        parts.append(piece)
    return "".join(parts)


def indent_width(line: str) -> int | None:
    raw = line.rstrip("\r\n")
    if raw.strip() == "":
        return -1
    prefix = len(raw) - len(raw.lstrip(" \t"))
    if "\t" in raw[:prefix]:
        return None
    return prefix


def line_kind(line: str) -> str:
    width = indent_width(line)
    if width is None:
        return "bad"
    if width < 0:
        return "blank"
    content = line.rstrip("\r\n")[width:]
    if content == "-" or content.startswith("- "):
        return "collection"
    if KEY_RE.match(content):
        return "collection"
    return "plain"


def parse_collection(lines: list[str], start: int, close: int, parent_indent: int):
    index = start
    while index < close and not lines[index].strip():
        index += 1
    if index >= close:
        return None, start
    indent = indent_width(lines[index])
    if indent is None or indent <= parent_indent:
        return None, start
    content = lines[index].rstrip("\r\n")[indent:]
    if content == "-" or content.startswith("- "):
        return parse_list(lines, index, close, indent)
    if KEY_RE.match(content):
        return parse_map(lines, index, close, indent)
    return None, start


def parse_map(lines: list[str], start: int, close: int, indent: int):
    index = start
    mapping: dict[str, object] = {}
    while index < close:
        if not lines[index].strip():
            index += 1
            continue
        current = indent_width(lines[index])
        if current is None:
            return None, index
        if current < indent:
            break
        if current != indent:
            return None, index
        content = lines[index].rstrip("\r\n")[current:]
        matched = KEY_RE.match(content)
        if not matched or matched.group(1) in mapping:
            return None, index
        key, rest = matched.group(1), matched.group(2)
        value_text = rest[1:] if rest.startswith(" ") else rest
        value, next_index = stored_value(lines, index, close, indent, value_text.strip())
        if value is None:
            return None, index
        mapping[key] = value
        index = next_index
    return mapping, index


def parse_list(lines: list[str], start: int, close: int, indent: int):
    index = start
    items = []
    while index < close:
        if not lines[index].strip():
            index += 1
            continue
        current = indent_width(lines[index])
        if current is None:
            return None, index
        if current < indent:
            break
        if current != indent:
            return None, index
        content = lines[index].rstrip("\r\n")[current:]
        if content == "-":
            payload = ""
        elif content.startswith("- "):
            payload = content[2:]
        else:
            return None, index
        value, next_index = parse_list_item(lines, index, close, indent, payload)
        if value is None:
            return None, index
        items.append(value)
        index = next_index
    return items, index


def parse_list_item(lines: list[str], index: int, close: int, indent: int, payload: str):
    if KEY_RE.match(payload or ""):
        return parse_dashed_mapping(lines, index, close, indent, payload)
    indicator = payload.strip()
    following = index + 1
    if indicator == "" and following < close and (indent_width(lines[following]) or -1) > indent:
        return parse_collection(lines, following, close, indent)
    decoded = decode_scalar(indicator) if indicator else ""
    if indicator and decoded is None:
        return None, index
    if following < close and (indent_width(lines[following]) or -1) > indent:
        continued, next_index = read_plain_lines(lines, following, close, decoded)
        if continued is None:
            return None, index
        return continued, next_index
    return decoded, index + 1


def parse_dashed_mapping(lines: list[str], index: int, close: int, dash_indent: int, payload: str):
    matched = KEY_RE.match(payload)
    if not matched:
        return None, index
    key_indent = dash_indent + 2
    key, rest = matched.group(1), matched.group(2)
    value_text = rest[1:] if rest.startswith(" ") else rest
    value, next_index = stored_value(lines, index, close, key_indent, value_text.strip())
    if value is None:
        return None, index
    mapping: dict[str, object] = {key: value}
    rest_map, next_index = parse_map(lines, next_index, close, key_indent)
    if rest_map is None:
        return None, index
    for sibling, sibling_value in rest_map.items():
        if sibling in mapping:
            return None, index
        mapping[sibling] = sibling_value
    return mapping, next_index


def stored_value(lines: list[str], key_line: int, close: int, key_indent: int, indicator: str):
    block = BLOCK_RE.fullmatch(indicator)
    if block and block.group(3):
        return None, key_line
    if block:
        content, next_index = read_block(lines, key_line + 1, close)
        return render_block(content, block.group(1), block.group(2) or ""), next_index
    decoded = decode_scalar(indicator) if indicator else ""
    if indicator and decoded is None:
        return None, key_line
    if indicator == "":
        nxt = key_line + 1
        while nxt < close and not lines[nxt].strip():
            nxt += 1
        if nxt < close:
            width = indent_width(lines[nxt])
            if width is None:
                return None, key_line
            if width > key_indent:
                kind = line_kind(lines[nxt])
                if kind == "collection":
                    return parse_collection(lines, nxt, close, key_indent)
                if kind == "plain":
                    return read_plain_lines(lines, nxt, close, "")
                return None, key_line
        return "", key_line + 1
    nxt = key_line + 1
    if nxt < close and lines[nxt].strip() and (indent_width(lines[nxt]) or -1) > key_indent:
        continued, next_index = read_plain_lines(lines, nxt, close, decoded)
        if continued is None:
            return None, key_line
        return continued, next_index
    return decoded, key_line + 1


def read_plain_lines(lines: list[str], start: int, close: int, first: str) -> tuple[str | None, int]:
    parts = [first] if first else []
    index = start
    while index < close:
        line = lines[index]
        if not line.strip() or line[0] not in " \t":
            break
        content = line.strip()
        if NESTED_RE.match(content):
            return None, index
        parts.append(content)
        index += 1
    return " ".join(parts), index


def decode_scalar(raw: str) -> str | None:
    if raw[:1] in "{[&*!":
        return None
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        inner = raw[1:-1]
        if raw[0] == "'":
            if "'" in inner.replace("''", ""):
                return None
            return inner.replace("''", "'")
        return decode_double(inner)
    return raw


def decode_double(inner: str) -> str | None:
    out = []
    index = 0
    while index < len(inner):
        if inner[index] != "\\":
            out.append(inner[index])
            index += 1
            continue
        if index + 1 >= len(inner):
            return None
        mapped = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "r": "\r"}.get(inner[index + 1])
        if mapped is None:
            return None
        out.append(mapped)
        index += 2
    return "".join(out)


def replace_staged_files(replacements: list[tuple[Path, str]]) -> None:
    """Stage every new file, then os.replace it onto the destination. A failed replace puts pre-images back."""
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, bytes]] = []
    try:
        for dest, text in replacements:
            handle, name = tempfile.mkstemp(dir=str(dest.parent), prefix=".compressor-", suffix=".tmp")
            os.close(handle)
            tmp = Path(name)
            tmp.write_bytes(text.encode("utf-8"))
            staged.append((tmp, dest))
        for tmp, dest in staged:
            backups.append((dest, dest.read_bytes()))
            os.replace(tmp, dest)
    except Exception:
        for dest, preimage in backups:
            dest.write_bytes(preimage)
        raise
    finally:
        for tmp, _dest in staged:
            if tmp.exists():
                tmp.unlink()


def strip_fences(text: str) -> str:
    lines = text.splitlines(keepends=True)
    hidden = fence_line_indexes(walk_fences(lines))
    return "".join(line for index, line in enumerate(lines) if index not in hidden)


def fence_marker(line: str) -> tuple[str, int] | None:
    body = line.lstrip(" ")
    if len(line) - len(body) > 3:
        return None
    for char in ("`", "~"):
        count = 0
        for item in body:
            if item != char:
                break
            count += 1
        if count >= 3:
            return char, count
    return None


def unclosed_fence(text: str) -> bool:
    return any(not closed for _start, _end, closed in walk_fences(text.splitlines()))


def fence_closes(line: str, opener: tuple[str, int]) -> bool:
    marker = fence_marker(line)
    if marker is None or marker[0] != opener[0] or marker[1] < opener[1]:
        return False
    return line.strip() == marker[0] * marker[1]


def protected_sequences(text: str) -> tuple:
    return (tuple(fenced_blocks(text)), tuple(inline_codes(text)), tuple(absolute_urls(text)))


def fenced_blocks(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    return ["".join(lines[start:end]) for start, end, _closed in walk_fences(lines)]


def walk_fences(lines: list[str]) -> list[tuple[int, int, bool]]:
    spans = []
    index = 0
    while index < len(lines):
        opener = fence_marker(lines[index])
        if opener is None:
            index += 1
            continue
        start = index
        index += 1
        while index < len(lines) and not fence_closes(lines[index], opener):
            index += 1
        closed = index < len(lines)
        if closed:
            index += 1
        spans.append((start, index, closed))
    return spans


def fence_line_indexes(spans: list[tuple[int, int, bool]]) -> set[int]:
    indexes: set[int] = set()
    for start, end, _closed in spans:
        indexes.update(range(start, end))
    return indexes


def inline_codes(text: str) -> list[str]:
    spans = []
    for line in outside_fences(text):
        spans.extend(inline_codes_in(line))
    return spans


def inline_codes_in(line: str) -> list[str]:
    spans = []
    index = 0
    while index < len(line):
        if line[index] != "`":
            index += 1
            continue
        width = 0
        while index + width < len(line) and line[index + width] == "`":
            width += 1
        close = index + width
        found = None
        while close < len(line):
            if line[close] != "`":
                close += 1
                continue
            run = 0
            while close + run < len(line) and line[close + run] == "`":
                run += 1
            if run == width:
                found = close + run
                break
            close += run
        if found is None:
            break
        spans.append(line[index:found])
        index = found
    return spans


def absolute_urls(text: str) -> list[str]:
    return [match.group(0).rstrip(".,;:!?\"'") for match in URL_RE.finditer(text)]


def unified(name: str, before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile="a/" + name,
        tofile="b/" + name,
    ))


def ordered(names: list[str]) -> list[str]:
    rank = {name: index for index, name in enumerate(FAILURE_ORDER)}
    return sorted(set(names), key=lambda item: rank.get(item, len(FAILURE_ORDER)))


def empty_report(failures: list[str]) -> dict:
    return {
        "ok": not failures,
        "failures": failures,
        "words_before": 0,
        "words_after": 0,
        "files": [],
        "skipped": [],
        "unresolved": [],
        "diffs": {},
        "description_chars_before": None,
        "description_chars_after": None,
        "description_cap": None,
        "sibling_median": None,
    }


def emit(report: dict) -> None:
    json.dump(report, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    sys.exit(main())
