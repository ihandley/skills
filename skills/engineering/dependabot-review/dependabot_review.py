#!/usr/bin/env python3
"""dependabot-review commands. Each command prints one JSON object."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import engine

SKILL_DIR = Path(__file__).resolve().parent


def emit(obj, code=0):
    sys.stdout.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    return code


def run(argv, cwd=None, timeout=60):
    proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise engine.Stop((proc.stderr or proc.stdout or "command failed").strip())
    return proc.stdout


def ticketer_script():
    env = os.environ.get("DEPENDABOT_REVIEW_TICKETER")
    if env:
        return Path(env)
    candidates = [
        SKILL_DIR.parents[1] / "productivity" / "ticketer" / "ticketer.py",
        Path.home() / ".claude" / "skills" / "ticketer" / "ticketer.py",
        Path.home() / ".agents" / "skills" / "ticketer" / "ticketer.py",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise engine.Stop("ticketer.py was not found")


def locate(cwd):
    raw = run([sys.executable, str(ticketer_script()), "locate", "--cwd", str(cwd)])
    info = json.loads(raw)
    if not info.get("config_exists"):
        raise engine.Stop("ticketer has no config for %s" % cwd)
    return info


def checkout_repo(cwd):
    url = run(["git", "-C", str(cwd), "remote", "get-url", "origin"]).strip()
    slug = engine.remote_slug(url)
    if not slug:
        raise engine.Stop("origin remote is not a GitHub repo")
    return slug


def gh_json(args, cwd):
    return json.loads(run(["gh", *args], cwd=cwd))


def changelog_repo(package):
    ecosystem, name = package["ecosystem"], package["name"]
    if ecosystem == "gomod":
        match = __import__("re").match(r"github\.com/([^/]+)/([^/]+)", name)
        return "%s/%s" % match.groups() if match else None
    if ecosystem == "github-actions":
        parts = name.split("/")
        return "%s/%s" % (parts[0], parts[1]) if len(parts) >= 2 else None
    if ecosystem == "npm":
        try:
            raw = run(["npm", "view", name, "repository.url", "--json"], timeout=30)
        except engine.Stop:
            return None
        text = raw.strip().strip('"')
        slug = engine.remote_slug(text)
        return slug
    return None


def fetch_changelog(repo):
    for filename in ("CHANGELOG.md", "CHANGES.md", "HISTORY.md"):
        proc = subprocess.run(
            ["gh", "api", "-H", "Accept: application/vnd.github.raw",
             "/repos/%s/contents/%s" % (repo, filename)],
            capture_output=True, text=True, timeout=30, check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            text = proc.stdout
            if len(text) > 24000:
                text = text[:24000] + "\n\n[truncated]\n"
            return text
    return None


def packet_for(pr_text, cwd):
    checkout = checkout_repo(cwd)
    pr = engine.parse_pr_ref(pr_text, checkout)
    if not engine.same_repo(checkout, pr):
        raise engine.Stop("checkout is %s; pull request is %s/%s" % (checkout, pr["owner"], pr["repo"]))
    repo = "%s/%s" % (pr["owner"], pr["repo"])
    view = gh_json(["pr", "view", str(pr["number"]), "--repo", repo, "--json", "title,labels,statusCheckRollup"], cwd)
    diff = run(["gh", "pr", "diff", str(pr["number"]), "--repo", repo], cwd=cwd)
    packages = engine.parse_diff(diff)
    labels = [item.get("name", "") for item in view.get("labels") or []]
    security = any("security" in label.casefold() for label in labels)
    pieces, missing = [], False
    for package in packages:
        source = changelog_repo(package)
        text = fetch_changelog(source) if source else None
        if not text:
            missing = True
            continue
        pieces.append("## %s\n\n%s" % (package["name"], text.strip()))
    usage = []
    for package in packages:
        for hit in engine.usage_hits(cwd, package["name"]):
            hit["package"] = package["name"]
            usage.append(hit)
    return {
        "ok": True,
        "pr": {**pr, "title": view.get("title") or ""},
        "packages": packages,
        "security": security,
        "changelog_missing": missing or not pieces,
        "changelog": "\n\n".join(pieces),
        "ci": engine.ci_from_checks(view.get("statusCheckRollup") or []),
        "usage": usage,
    }


def load_template(info, issue_type):
    config_path = Path(info["config_path"])
    config = __import__("tomllib").loads(config_path.read_text(encoding="utf-8"))
    slug = issue_type.casefold()
    dirs = []
    if config.get("template_dir"):
        dirs.append(config_path.parent / config["template_dir"])
    script = ticketer_script()
    dirs.append(script.parent / "templates")
    for directory in dirs:
        candidate = directory / ("%s.md" % slug)
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return ""


def cmd_packet(args):
    try:
        payload = packet_for(args.pr, Path(args.cwd or os.getcwd()).resolve())
    except engine.Stop as exc:
        return emit({"ok": False, "error": exc.message}, engine.EXIT_STOP)
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return emit(payload)


def cmd_decide(args):
    packet = json.loads(Path(args.packet).read_text(encoding="utf-8"))
    verdict = json.loads(Path(args.verdict).read_text(encoding="utf-8"))
    if args.outcomes and args.tracker:
        outcomes_path = args.outcomes
        outcomes = engine.load_outcomes(outcomes_path, args.tracker)
        tracker = args.tracker
        template = Path(args.template).read_text(encoding="utf-8") if args.template else ""
    else:
        info = locate(Path(args.cwd or os.getcwd()).resolve())
        tracker = info["team"]
        outcomes_path = engine.outcomes_home() / "outcomes.toml"
        outcomes = engine.load_outcomes(outcomes_path, tracker)
        template = load_template(info, "Task")
    try:
        state = engine.build_state(packet, verdict, Path(args.root or args.cwd or os.getcwd()), outcomes)
    except engine.Stop as exc:
        return emit({"ok": False, "error": exc.message}, engine.EXIT_STOP)
    state["tracker"] = tracker
    state["ticket"] = engine.ticket_payload(state, template)
    if args.out:
        Path(args.out).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    code = engine.EXIT_OUTCOMES if state["outcomes_missing"] else 0
    return emit({
        "ok": code == 0,
        "error": None if code == 0 else "outcomes section %r is missing from %s" % (tracker, outcomes_path),
        "review": state["review"],
        "code_change": state["code_change"],
        "status_name": state["status_name"],
        "tracker": tracker,
        "summary": state["summary"],
        "ticket": state["ticket"],
    }, code)


def load_state(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def cmd_comment(args):
    if args.confirm not in {"yes", "replace"}:
        return emit({"ok": False, "error": "pass --confirm yes after the user agrees, or --confirm replace"}, engine.EXIT_STOP)
    state = load_state(args.state)
    pr = state["pr"]
    repo = "%s/%s" % (pr["owner"], pr["repo"])
    view = gh_json(["pr", "view", str(pr["number"]), "--repo", repo, "--json", "comments"], Path(args.cwd or os.getcwd()))
    bodies = [item.get("body") or "" for item in view.get("comments") or []]
    if any("dependabot-audit:v1" in body for body in bodies) and args.confirm != "replace":
        return emit({"ok": True, "posted": False, "reason": "prior comment"})
    body = engine.render_comment(state)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(body)
        path = handle.name
    try:
        run(["gh", "pr", "comment", str(pr["number"]), "--repo", repo, "--body-file", path])
    except engine.Stop as exc:
        return emit({"ok": False, "posted": False, "error": exc.message}, engine.EXIT_STOP)
    finally:
        Path(path).unlink(missing_ok=True)
    return emit({"ok": True, "posted": True})


def cmd_find_ticket(args):
    state = load_state(args.state)
    url = state["pr"]["url"]
    tracker = state.get("tracker")
    if tracker == "github":
        repo = "%s/%s" % (state["pr"]["owner"], state["pr"]["repo"])
        found = gh_json(["issue", "list", "--repo", repo, "--state", "all", "--search", "%s in:body" % url, "--json", "number,title,url"], Path(args.cwd or os.getcwd()))
        return emit({"ok": True, "tracker": tracker, "matches": found})
    return emit({
        "ok": True,
        "tracker": tracker,
        "search": {"jql": 'text ~ "%s"' % url},
    })


def cmd_status(args):
    state = load_state(args.state)
    transitions = json.loads(Path(args.transitions).read_text(encoding="utf-8")) if args.transitions else []
    fields = json.loads(Path(args.fields).read_text(encoding="utf-8")) if args.fields else []
    if isinstance(transitions, dict):
        transitions = transitions.get("transitions") or transitions.get("values") or []
    if isinstance(fields, dict):
        fields = fields.get("fields") or fields.get("values") or []
    try:
        plan = engine.status_plan(state, transitions, fields)
    except engine.Stop as exc:
        return emit({"ok": False, "error": exc.message}, engine.EXIT_STATUS)
    return emit({"ok": True, **plan})


def cmd_brief(args):
    state = load_state(args.state)
    prior = Path(args.prior_file).read_text(encoding="utf-8") if args.prior_file else ""
    return emit({"ok": True, **engine.render_brief(state, prior)})


def parser():
    top = argparse.ArgumentParser(prog="dependabot_review.py")
    top.add_argument("--cwd", default=None)
    sub = top.add_subparsers(dest="command", required=True)

    packet = sub.add_parser("packet")
    packet.add_argument("pr")
    packet.add_argument("--out")
    packet.set_defaults(fn=cmd_packet)

    decide = sub.add_parser("decide")
    decide.add_argument("--packet", required=True)
    decide.add_argument("--verdict", required=True)
    decide.add_argument("--root")
    decide.add_argument("--out")
    decide.add_argument("--outcomes")
    decide.add_argument("--tracker")
    decide.add_argument("--template")
    decide.set_defaults(fn=cmd_decide)

    comment = sub.add_parser("comment")
    comment.add_argument("--state", required=True)
    comment.add_argument("--confirm", required=True)
    comment.set_defaults(fn=cmd_comment)

    find = sub.add_parser("find-ticket")
    find.add_argument("--state", required=True)
    find.set_defaults(fn=cmd_find_ticket)

    status = sub.add_parser("status")
    status.add_argument("--state", required=True)
    status.add_argument("--transitions")
    status.add_argument("--fields")
    status.set_defaults(fn=cmd_status)

    brief = sub.add_parser("brief")
    brief.add_argument("--state", required=True)
    brief.add_argument("--prior-file")
    brief.set_defaults(fn=cmd_brief)
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        code = args.fn(args)
    except engine.Stop as exc:
        return emit({"ok": False, "error": exc.message}, engine.EXIT_STOP)
    return code


if __name__ == "__main__":
    sys.exit(main())
