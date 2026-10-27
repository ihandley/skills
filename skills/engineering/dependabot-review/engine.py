"""Pure decisions for dependabot-review. Network and git stay in the CLI."""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

VERDICTS = ("Merge", "Verify", "Investigate", "Hold")
CHANGELOG_MISSING = "changelog not found"
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "target", ".terraform",
    "coverage", ".next",
}
TEST_PARTS = {"test", "tests", "__tests__", "fixture", "fixtures", "spec", "specs"}
ECOSYSTEMS = ("npm", "maven", "gomod", "cargo", "terraform", "github-actions")

EXIT_STOP = 2
EXIT_OUTCOMES = 3
EXIT_STATUS = 4


class Stop(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def bare_version(value):
    text = value.strip().strip('"').strip("'")
    text = re.sub(r"^[\^~>=<vV\s]+", "", text)
    text = text.split()[0]
    return text.split("+")[0].split("-")[0]


def classify_bump(old, new):
    def parts(value):
        match = re.match(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", bare_version(value))
        if not match:
            return None
        return tuple(int(group or 0) for group in match.groups())

    left, right = parts(old), parts(new)
    if not left or not right or left == right:
        return "unknown"
    if left[0] != right[0]:
        return "major"
    if left[1] != right[1]:
        return "minor"
    return "patch"


def ecosystem_of(path):
    name = Path(path).name
    if name in {"package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json"}:
        return "npm"
    if name == "pom.xml":
        return "maven"
    if name in {"go.mod", "go.sum"}:
        return "gomod"
    if name in {"Cargo.toml", "Cargo.lock"}:
        return "cargo"
    if name == ".terraform.lock.hcl" or path.endswith(".tf"):
        return "terraform"
    normalized = path.replace("\\", "/")
    if normalized.startswith(".github/workflows/") or normalized.startswith(".github/actions/") or "/.github/workflows/" in f"/{normalized}" or "/.github/actions/" in f"/{normalized}":
        return "github-actions"
    return None


def split_diff(diff):
    files = []
    for part in re.split(r"(?m)^diff --git ", diff):
        if not part.strip():
            continue
        match = re.match(r"a/(.+?) b/(.+?)(?:\n|$)", part)
        if not match:
            continue
        path = match.group(1) if match.group(2) == "dev/null" else match.group(2)
        files.append((path, part))
    return files


def _diff_lines(file_diff):
    rows = []
    for line in file_diff.splitlines():
        if line.startswith(("diff ", "index ", "---", "+++", "@@", "new file", "deleted file", "similarity", "rename")):
            continue
        if line[:1] in "+- ":
            rows.append((line[0], line[1:]))
    return rows


def _pair_versions(removed, added):
    bumps = []
    used = set()
    for name, old in removed:
        for index, (new_name, new) in enumerate(added):
            if index in used or new_name != name or old == new:
                continue
            used.add(index)
            bumps.append((name, old, new))
            break
    return bumps


_JSON_DEP = re.compile(r"""["']([^"']+)["']\s*:\s*["']([^"']+)["']""")
_GO_DEP = re.compile(r"(?:require\s+)?(\S+)\s+v(\S+)")
_CARGO_DEP = re.compile(r"^([A-Za-z0-9_-]+)\s*=\s*\"([^\"]+)\"")
_USES = re.compile(r"uses:\s*([^@\s]+)@(\S+)")
_ARTIFACT = re.compile(r"<artifactId>([^<]+)</artifactId>")
_VERSION = re.compile(r"<version>([^<]+)</version>")
_TF_SOURCE = re.compile(r'(?:source|name)\s*=\s*"([^"]+)"')
_TF_VERSION = re.compile(r'version\s*=\s*"([^"]+)"')


def _json_deps(lines):
    found = []
    for line in lines:
        match = _JSON_DEP.search(line)
        if match and match.group(1) not in {"name", "version", "license"}:
            found.append((match.group(1), match.group(2)))
    return found


def _go_deps(lines):
    found = []
    for line in lines:
        match = _GO_DEP.search(line.strip())
        if match and not match.group(1).endswith(".zip"):
            found.append((match.group(1), match.group(2)))
    return found


def _cargo_deps(lines):
    found = []
    for line in lines:
        match = _CARGO_DEP.match(line.strip())
        if match and match.group(1) not in {"name", "version", "edition"}:
            found.append(match.groups())
    return found


def _uses(lines):
    found = []
    for line in lines:
        match = _USES.search(line)
        if match:
            action = "/".join(match.group(1).split("/")[:2])
            found.append((action, match.group(2)))
    return found


def _pom_deps(file_diff):
    artifact = None
    pending = None
    removed, added = [], []
    for sign, text in _diff_lines(file_diff):
        found = _ARTIFACT.search(text)
        if found and sign != "-":
            artifact = found.group(1)
            pending = None
        version = _VERSION.search(text)
        if not version or not artifact:
            continue
        if sign == "-":
            pending = (artifact, version.group(1))
        elif sign == "+" and pending and pending[0] == artifact:
            removed.append(pending)
            added.append((artifact, version.group(1)))
            pending = None
    return _pair_versions(removed, added)


def _tf_deps(file_diff):
    source = None
    pending = None
    removed, added = [], []
    for sign, text in _diff_lines(file_diff):
        found = _TF_SOURCE.search(text)
        if found and sign != "-":
            source = found.group(1)
            pending = None
        version = _TF_VERSION.search(text)
        if not version or not source:
            continue
        if sign == "-":
            pending = (source, version.group(1))
        elif sign == "+" and pending and pending[0] == source:
            removed.append(pending)
            added.append((source, version.group(1)))
            pending = None
    return _pair_versions(removed, added)


def parse_file(path, file_diff):
    ecosystem = ecosystem_of(path)
    if ecosystem is None:
        return []
    removed, added, _context = [], [], []
    for sign, text in _diff_lines(file_diff):
        if sign == "-":
            removed.append(text)
        elif sign == "+":
            added.append(text)
    if ecosystem == "npm" and Path(path).name == "package.json":
        pairs = _pair_versions(_json_deps(removed), _json_deps(added))
    elif ecosystem == "gomod" and Path(path).name == "go.mod":
        pairs = _pair_versions(_go_deps(removed), _go_deps(added))
    elif ecosystem == "cargo" and Path(path).name == "Cargo.toml":
        pairs = _pair_versions(_cargo_deps(removed), _cargo_deps(added))
    elif ecosystem == "maven":
        pairs = _pom_deps(file_diff)
    elif ecosystem == "github-actions":
        pairs = _pair_versions(_uses(removed), _uses(added))
    elif ecosystem == "terraform":
        pairs = _tf_deps(file_diff)
    else:
        pairs = []
    packages = []
    for name, old, new in pairs:
        packages.append({
            "ecosystem": ecosystem,
            "name": name,
            "old": bare_version(old),
            "new": bare_version(new),
            "bump": classify_bump(old, new),
        })
    return packages


def parse_diff(diff):
    files = split_diff(diff)
    if not files:
        raise Stop("the diff has no files")
    unknown = [path for path, _diff in files if ecosystem_of(path) is None]
    if unknown and len(unknown) == len(files):
        raise Stop("unknown ecosystem: %s" % ", ".join(sorted(unknown)))
    if unknown:
        raise Stop("mixed diff: %s" % ", ".join(sorted(unknown)))
    packages = []
    seen = set()
    for path, file_diff in files:
        for package in parse_file(path, file_diff):
            key = (package["ecosystem"], package["name"])
            if key in seen:
                continue
            seen.add(key)
            packages.append(package)
    if not packages:
        raise Stop("no package bump parsed from the diff")
    return packages


def is_test_path(path):
    parts = {part.lower() for part in Path(path).parts}
    if parts & TEST_PARTS:
        return True
    name = Path(path).name.lower()
    return (
        name.startswith("test_")
        or name.endswith("_test.go")
        or ".test." in name
        or ".spec." in name
    )


def grep_symbol(root, symbol):
    if not symbol or not Path(root).is_dir():
        return []
    pattern = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(symbol))
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS and name not in TEST_PARTS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if is_test_path(path.relative_to(root)):
                continue
            try:
                if path.stat().st_size > 1_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if pattern.search(text):
                hits.append(str(path.relative_to(root)))
                if len(hits) >= 20:
                    return hits
    return hits


def usage_hits(root, name):
    return [{"path": path, "test": False} for path in grep_symbol(root, name)]


def schema_errors(verdict):
    errors = []
    if not isinstance(verdict, dict):
        return ["verdict must be an object"]
    if verdict.get("verdict") not in VERDICTS:
        errors.append("verdict must be one of: %s" % ", ".join(VERDICTS))
    if not isinstance(verdict.get("one_line_reason"), str) or not verdict.get("one_line_reason", "").strip():
        errors.append("one_line_reason must be a non-empty string")
    breaks = verdict.get("breaks")
    if not isinstance(breaks, list):
        errors.append("breaks must be a list")
    else:
        for index, item in enumerate(breaks):
            kind = item.get("kind") if isinstance(item, dict) else None
            if kind == "symbol" and not str(item.get("name", "")).strip():
                errors.append("breaks[%d] needs a name" % index)
            elif kind == "behavior" and not str(item.get("summary", "")).strip():
                errors.append("breaks[%d] needs a summary" % index)
            elif kind not in {"symbol", "behavior"}:
                errors.append("breaks[%d] kind must be symbol or behavior" % index)
    impact = verdict.get("impact")
    if not isinstance(impact, list):
        errors.append("impact must be a list")
    else:
        for index, item in enumerate(impact):
            if not isinstance(item, dict) or not str(item.get("area", "")).strip() or not str(item.get("line", "")).strip():
                errors.append("impact[%d] needs area and line" % index)
    if "security" in verdict and not isinstance(verdict.get("security"), bool):
        errors.append("security must be a boolean")
    return errors


def _append_break(breaks, summary):
    if any(item.get("kind") == "behavior" and item.get("summary") == summary for item in breaks):
        return breaks
    return breaks + [{"kind": "behavior", "summary": summary}]


def apply_breaks(packet, verdict):
    breaks = [dict(item) for item in verdict.get("breaks", [])]
    if packet.get("changelog_missing"):
        breaks = _append_break(breaks, CHANGELOG_MISSING)
    if verdict.get("verdict") == "Hold" and not breaks:
        breaks = _append_break(breaks, verdict.get("one_line_reason", "").strip() or "Hold")
    return breaks


def code_change_line(breaks, symbol_hits):
    for item in breaks:
        if item.get("kind") == "behavior" and item.get("summary") != CHANGELOG_MISSING:
            return item["summary"]
    for name in symbol_hits:
        return "%s needs a code change" % name
    for item in breaks:
        if item.get("kind") == "behavior":
            return item["summary"]
    return ""


def summary_line(packages, number):
    if len(packages) == 1:
        package = packages[0]
        return "deps | %s %s→%s (PR #%s)" % (package["name"], package["old"], package["new"], number)
    return "deps | %s+… (PR #%s)" % (packages[0]["name"], number)


def security_flag(packet, verdict):
    return bool(packet.get("security") or verdict.get("security"))


def outcomes_home():
    return Path(os.environ.get("TICKETER_HOME") or Path.home() / ".config" / "ticketer")


def load_outcomes(path, tracker):
    file = Path(path)
    if not file.is_file():
        return None
    data = tomllib.loads(file.read_text(encoding="utf-8"))
    section = data.get(tracker)
    if not isinstance(section, dict):
        return None
    return section


def status_name(outcomes, code_change):
    if not outcomes:
        return None
    key = "code_change_status" if code_change else "no_change_status"
    value = outcomes.get(key)
    return value if isinstance(value, str) and value.strip() else None


def flag_action(outcomes, code_change):
    if not outcomes or "code_change_flag" not in outcomes:
        return None
    if code_change:
        return outcomes.get("code_change_flag") or ""
    return ""


def fill_template(template, sections):
    lines = []
    current = None

    def flush():
        if current is None:
            return
        body = sections.get(current.casefold(), "").strip()
        lines.append("## %s" % current)
        lines.append("")
        lines.append(body)
        lines.append("")

    for line in template.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            flush()
            current = match.group(1).strip()
            bucket = []
        elif current is None:
            continue
    flush()
    return "\n".join(lines).strip() + "\n"


def description_sections(state):
    url = state["pr"]["url"]
    lead = state["code_change_line"] if state["code_change"] else "No code change."
    objective = "%s\n\n%s" % (lead, summary_line(state["packages"], state["pr"]["number"]))
    detail = [state["verdict"]["one_line_reason"], "", "Pull request: %s" % url]
    for item in state["breaks"]:
        if item["kind"] == "behavior":
            detail.append("- %s" % item["summary"])
        else:
            detail.append("- symbol %s" % item["name"])
    for item in state["verdict"].get("impact", []):
        detail.append("- %s: %s" % (item["area"], item["line"]))
    if state["security"]:
        value = "This bump includes a security fix."
    else:
        value = "This keeps the dependency current."
    criteria = ["- The pull request %s is merged." % url]
    if state["code_change"]:
        criteria.append("- The required code change is in the branch before merge.")
    text = {
        "objective": objective,
        "context": objective,
        "description": "\n".join(detail),
        "business value / impact": value,
        "business value": value,
        "acceptance criteria": "\n".join(criteria),
    }
    return text


def render_description(template, state):
    sections = description_sections(state)
    if not template:
        return "## Context\n\n%s\n" % sections["context"]
    known = set(sections)
    rendered = {}
    for line in template.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if not match:
            continue
        heading = match.group(1).strip()
        key = heading.casefold()
        if key in known:
            rendered[key] = sections[key]
        else:
            rendered[key] = "Pull request: %s." % state["pr"]["url"]
    return fill_template(template, rendered)


def render_review(state):
    lines = []
    if state["code_change"]:
        lines.append(state["code_change_line"])
        lines.append("")
    lines.append("## %s" % summary_line(state["packages"], state["pr"]["number"]))
    lines.append("")
    lines.append("Verdict: %s." % state["verdict"]["verdict"])
    ci = state["ci"]
    if ci.get("names"):
        lines.append("CI %s: %s." % (ci.get("state", "unknown"), ", ".join(ci["names"])))
    else:
        lines.append("CI %s." % ci.get("state", "unknown"))
    lines.append("")
    lines.append(state["verdict"]["one_line_reason"])
    if state["breaks"]:
        lines.append("")
        lines.append("Breaks:")
        for item in state["breaks"]:
            if item["kind"] == "behavior":
                lines.append("- %s" % item["summary"])
            else:
                hit = "hit" if item["name"] in state["symbol_hits"] else "miss"
                lines.append("- %s (%s)" % (item["name"], hit))
    if state["verdict"].get("impact"):
        lines.append("")
        for item in state["verdict"]["impact"]:
            lines.append("- %s: %s" % (item["area"], item["line"]))
    return "\n".join(lines).strip() + "\n"


def comment_line(state):
    parts = []
    if state["code_change"]:
        parts.append(state["code_change_line"])
    ci = state["ci"]
    if ci.get("state") in {"fail", "pending"} and ci.get("names"):
        parts.append("CI %s: %s" % (ci["state"], ", ".join(ci["names"])))
    if not parts:
        parts.append(state["verdict"]["one_line_reason"])
    return ". ".join(parts)


def render_comment(state):
    body = "\n".join([
        "## Dependabot review",
        "",
        "**Verdict:** %s" % state["verdict"]["verdict"],
        "",
        comment_line(state),
        "",
        "<details>",
        "<summary>Full review</summary>",
        "",
        render_review(state).rstrip(),
        "",
        "</details>",
        "",
        "<!-- dependabot-audit:v1 -->",
        "",
    ])
    return body


def marker(state):
    bit = "1" if state["code_change"] else "0"
    return "<!-- dependabot-review:v1 verdict=%s bit=%s -->" % (state["verdict"]["verdict"], bit)


def render_brief(state, prior=""):
    token = marker(state)
    if prior and token in prior:
        return {"post": False, "brief": "", "marker": token}
    lines = [state["code_change_line"] if state["code_change"] else "No code change."]
    lines.append("Verdict: %s." % state["verdict"]["verdict"])
    lines.append("Pull request: %s." % state["pr"]["url"])
    if state.get("status_name"):
        lines.append("Status: %s." % state["status_name"])
    lines.append(token)
    return {"post": True, "brief": "\n".join(lines), "marker": token}


def build_state(packet, verdict, root, outcomes):
    errors = schema_errors(verdict)
    if errors:
        raise Stop("; ".join(errors))
    breaks = apply_breaks(packet, verdict)
    symbol_hits = {}
    for item in breaks:
        if item.get("kind") == "symbol":
            symbol_hits[item["name"]] = grep_symbol(root, item["name"])
    hit_names = [name for name, paths in symbol_hits.items() if paths]
    code_change = any(item.get("kind") == "behavior" for item in breaks) or bool(hit_names)
    pr = packet["pr"]
    state = {
        "pr": pr,
        "packages": packet["packages"],
        "verdict": verdict,
        "breaks": breaks,
        "symbol_hits": hit_names,
        "code_change": code_change,
        "code_change_line": code_change_line(breaks, hit_names),
        "security": security_flag(packet, verdict),
        "ci": packet.get("ci") or {"state": "unknown", "names": []},
        "status_name": status_name(outcomes, code_change) if outcomes is not None else None,
        "flag": flag_action(outcomes, code_change) if outcomes is not None else None,
        "outcomes_missing": outcomes is None,
    }
    state["review"] = render_review(state)
    state["summary"] = summary_line(packet["packages"], pr["number"])
    state["priority"] = "High" if state["security"] else "Medium"
    return state


def ticket_payload(state, template):
    return {
        "summary": state["summary"],
        "description": render_description(template, state),
        "issue_type": "Task",
        "priority": state["priority"],
    }


def match_transition(transitions, name):
    for item in transitions or []:
        destination = item.get("to") if isinstance(item, dict) else None
        if isinstance(destination, dict) and destination.get("name") == name and item.get("id") is not None:
            return str(item["id"])
    return None


def flagged_field(fields):
    for item in fields or []:
        if isinstance(item, dict) and item.get("name") == "Flagged" and item.get("id"):
            return item["id"]
    return None


def status_plan(state, transitions, fields):
    plan = {"transition": None, "flag": None}
    if state.get("status_name"):
        transition_id = match_transition(transitions, state["status_name"])
        if transition_id is None:
            raise Stop("status %r is not a legal transition" % state["status_name"])
        plan["transition"] = {"id": transition_id, "name": state["status_name"]}
    if state.get("flag") is not None:
        field_id = flagged_field(fields)
        if field_id is None:
            raise Stop("the Flagged field is not on this issue type")
        value = [] if state["flag"] == "" else [{"value": state["flag"]}]
        plan["flag"] = {"field_id": field_id, "value": value}
    return plan


def ci_from_checks(checks):
    fail, pending, names = [], [], []
    for check in checks or []:
        name = check.get("name") or check.get("context") or "check"
        state = (check.get("state") or check.get("status") or check.get("conclusion") or "").upper()
        if state in {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "STARTUP_FAILURE"}:
            fail.append(name)
        elif state in {"PENDING", "IN_PROGRESS", "QUEUED", "WAITING", "REQUESTED", ""}:
            if state:
                pending.append(name)
        elif state not in {"SUCCESS", "SKIPPED", "NEUTRAL"}:
            pending.append(name)
    if fail:
        return {"state": "fail", "names": fail}
    if pending:
        return {"state": "pending", "names": pending}
    if not checks:
        return {"state": "unknown", "names": []}
    return {"state": "pass", "names": names}


def remote_slug(url):
    match = re.search(r"[:/]([^/:]+)/([^/]+?)(?:\.git)?/?$", url.strip())
    if not match:
        return None
    return "%s/%s" % (match.group(1), match.group(2))


def parse_pr_ref(text, default_repo=None):
    match = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", text)
    if match:
        owner, repo, number = match.groups()
        return {
            "owner": owner,
            "repo": repo,
            "number": int(number),
            "url": "https://github.com/%s/%s/pull/%s" % (owner, repo, number),
        }
    if re.fullmatch(r"\d+", text.strip()) and default_repo:
        owner, repo = default_repo.split("/", 1)
        number = int(text.strip())
        return {
            "owner": owner,
            "repo": repo,
            "number": number,
            "url": "https://github.com/%s/%s/pull/%s" % (owner, repo, number),
        }
    raise Stop("pass a GitHub pull request URL or number")


def same_repo(checkout, pr):
    return checkout.lower() == "%s/%s" % (pr["owner"], pr["repo"])
