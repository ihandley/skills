"""The subset of YAML these scripts read. No PyYAML.

Block maps, flow lists, flow maps, comments, and quoted scalars. Enough for
`~/.claude/aliases.yaml` and the fixtures. Not a general YAML parser.
"""

from __future__ import annotations

import re
from pathlib import Path


class YamlError(ValueError):
    pass


def load(path: str | Path) -> dict:
    return parse(Path(path).read_text())


def parse(text: str) -> dict:
    doc, _index = _block(text.splitlines(), 0, 0)
    if not isinstance(doc, dict):
        raise YamlError("the alias file must be a map")
    return doc


def _block(lines: list[str], index: int, indent: int) -> tuple[dict, int]:
    result: dict = {}
    while index < len(lines):
        raw = lines[index]
        if not raw.strip() or raw.lstrip().startswith("#"):
            index += 1
            continue
        current = len(raw) - len(raw.lstrip(" "))
        if current < indent:
            break
        if current != indent:
            raise YamlError(f"line {index + 1}: expected indent {indent}")
        body = raw.strip()
        if body.startswith("- "):
            raise YamlError(f"line {index + 1}: block lists are not used in the alias file")
        key, sep, value = body.partition(":")
        if not sep or not key.strip():
            raise YamlError(f"line {index + 1}: expected a key")
        value = value.strip()
        if value == "":
            child, index = _block(lines, index + 1, indent + 2)
            result[key.strip()] = child
            continue
        result[key.strip()] = _value(value, index + 1)
        index += 1
    return result, index


def _value(value: str, lineno: int):
    if value[0] in "[{":
        parsed, index = _flow(value, 0, lineno)
        if value[index:].strip():
            raise YamlError(f"line {lineno}: trailing {value[index:].strip()!r}")
        return parsed
    if value[0] == "'":
        parsed, index = _single(value, 0, lineno)
        if value[index:].strip():
            raise YamlError(f"line {lineno}: trailing {value[index:].strip()!r}")
        return parsed
    if value[0] == '"':
        parsed, index = _double(value, 0, lineno)
        if value[index:].strip():
            raise YamlError(f"line {lineno}: trailing {value[index:].strip()!r}")
        return parsed
    return _plain(value)


def _flow(text: str, index: int, lineno: int):
    opener = text[index]
    closer = "]" if opener == "[" else "}"
    index += 1
    items: list = []
    pairs: dict = {}
    while index < len(text):
        index = _skip(text, index)
        if text[index] == closer:
            return (items if opener == "[" else pairs), index + 1
        if opener == "{":
            key, index = _flow_scalar(text, index, lineno, ":}")
            index = _skip(text, index)
            if index >= len(text) or text[index] != ":":
                raise YamlError(f"line {lineno}: flow map key needs a colon")
            index += 1
            value, index = _flow_scalar(text, index, lineno, ",}")
            pairs[key] = value
        else:
            value, index = _flow_scalar(text, index, lineno, ",]")
            items.append(value)
        index = _skip(text, index)
        if index < len(text) and text[index] == ",":
            index += 1
            continue
        if index < len(text) and text[index] == closer:
            return (items if opener == "[" else pairs), index + 1
        raise YamlError(f"line {lineno}: flow value did not end")
    raise YamlError(f"line {lineno}: unclosed flow value")


def _flow_scalar(text: str, index: int, lineno: int, stops: str):
    index = _skip(text, index)
    if index >= len(text):
        raise YamlError(f"line {lineno}: flow value ended early")
    if text[index] in "[{":
        return _flow(text, index, lineno)
    if text[index] == "'":
        return _single(text, index, lineno)
    if text[index] == '"':
        return _double(text, index, lineno)
    start = index
    while index < len(text) and text[index] not in stops:
        index += 1
    return _plain(text[start:index].strip()), index


def _single(text: str, index: int, lineno: int) -> tuple[str, int]:
    index += 1
    chars: list[str] = []
    while index < len(text):
        if text[index] == "'":
            if index + 1 < len(text) and text[index + 1] == "'":
                chars.append("'")
                index += 2
                continue
            return "".join(chars), index + 1
        chars.append(text[index])
        index += 1
    raise YamlError(f"line {lineno}: unclosed quote")


def _double(text: str, index: int, lineno: int) -> tuple[str, int]:
    index += 1
    chars: list[str] = []
    while index < len(text):
        if text[index] == "\\":
            if index + 1 >= len(text):
                raise YamlError(f"line {lineno}: broken escape")
            escaped = text[index + 1]
            chars.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(escaped, escaped))
            index += 2
            continue
        if text[index] == '"':
            return "".join(chars), index + 1
        chars.append(text[index])
        index += 1
    raise YamlError(f"line {lineno}: unclosed quote")


def _plain(text: str):
    if text in ("true", "false"):
        return text == "true"
    if text in ("null", "~"):
        return None
    if re.fullmatch(r"-?(0|[1-9]\d*)", text):
        return int(text)
    return text


def _skip(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t":
        index += 1
    return index
