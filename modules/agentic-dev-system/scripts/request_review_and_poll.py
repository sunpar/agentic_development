#!/usr/bin/env python3
"""Post review request comments and poll PR review comments."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import time

KEYWORDS = ["request", "should", "must", "please", "need", "change", "fix", "clarify", "incorrect", "missing"]


def run(cmd: list[str], capture: bool = True):
    if capture:
        return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return subprocess.run(cmd, text=True)


def gh_available():
    return run(["which", "gh"], capture=True).returncode == 0 and run(["gh", "auth", "status"], capture=True).returncode == 0


def run_json(cmd: list[str]):
    rc = run(cmd, capture=True)
    if rc.returncode != 0:
        return None
    try:
        return json.loads(rc.stdout.strip())
    except Exception:
        return None


def current_repo():
    data = run_json(["gh", "repo", "view", "--json", "nameWithOwner"])
    if not data:
        return None
    return data.get("nameWithOwner")


def current_pr_number(repo=None):
    cmd = ["gh", "pr", "view", "--json", "number,url"]
    if repo:
        cmd.extend(["--repo", repo])
    data = run_json(cmd)
    if not data:
        return None, None
    return data.get("number"), data.get("url")


def build_review_body(providers, focus):
    focus = (focus or "").strip()
    lines = []
    if "codex" in providers:
        lines.append(f"@codex review for {focus}" if focus else "@codex review")
    if "copilot" in providers:
        lines.append(f"@copilot please review this PR for {focus}" if focus else "@copilot please review this PR")
    body = "\n".join(lines)
    if focus:
        body += "\n\nFocus:\n- " + "\n- ".join([f.strip() for f in focus.split(",") if f.strip()])
    return body


def post_request(pr_num: int, providers, focus, repo=None):
    body = build_review_body(providers, focus)
    cmd = ["gh", "pr", "comment", str(pr_num), "--body", body]
    if repo:
        cmd.extend(["--repo", repo])
    return run(cmd, capture=True)


def extract_actionable(items, src):
    out = []
    for item in items:
        body = item.get("body", "") or ""
        if any(k in body.lower() for k in KEYWORDS):
            out.append({
                "source": src,
                "author": item.get("author", {}).get("login", "unknown"),
                "url": item.get("url", ""),
                "body": body.strip(),
            })
    return out


def poll_pr(pr_num: int, repo=None):
    repo = repo or current_repo()
    if not repo:
        return []

    comments_url = f"repos/{repo}/pulls/{pr_num}/comments"
    reviews_url = f"repos/{repo}/pulls/{pr_num}/reviews"
    issue_comments_url = f"repos/{repo}/issues/{pr_num}/comments"

    comments = run_json(["gh", "api", comments_url])
    reviews = run_json(["gh", "api", reviews_url])
    issue_comments = run_json(["gh", "api", issue_comments_url])

    actionable = []
    if isinstance(comments, list):
        actionable.extend(extract_actionable(comments, "comment"))
    if isinstance(reviews, list):
        actionable.extend(extract_actionable(reviews, "review"))
    if isinstance(issue_comments, list):
        actionable.extend(extract_actionable(issue_comments, "issue-comment"))

    return actionable


def sanitize_for_json(obj):
    if isinstance(obj, set):
        return sorted(obj)
    return obj


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=["codex", "copilot", "both"], default="both")
    parser.add_argument("--focus", default="")
    parser.add_argument("--interval", type=int, default=20)
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--md", dest="md_path")
    parser.add_argument("--pr-number", type=int)
    parser.add_argument("--repo")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    providers = {"codex", "copilot"} if args.provider == "both" else {args.provider}

    if args.dry_run:
        pr_num = args.pr_number or "<current-pr>"
        pr_url = None
        print(f"DRY-RUN: would request review on PR #{pr_num} for {sorted(providers)}")
        if args.repo:
            print(f"DRY-RUN: repo {args.repo}")
        print(build_review_body(providers, args.focus))
        return 0

    if not gh_available():
        print("ERROR: gh unavailable or unauthenticated")
        return 3

    repo = args.repo or current_repo()
    pr_num = args.pr_number
    pr_url = None
    if not pr_num:
        pr_num, pr_url = current_pr_number(repo)
    if not pr_num:
        print("ERROR: cannot resolve current PR")
        return 4

    rc = post_request(pr_num, providers, args.focus, repo=repo)
    if rc.returncode != 0:
        print("ERROR: review request failed")
        return 5

    all_findings = []
    for cycle in range(args.cycles):
        if args.dry_run:
            break
        findings = poll_pr(pr_num, repo)
        all_findings.extend(findings)
        time.sleep(args.interval)

    # dedupe
    uniq = []
    seen = set()
    for f in all_findings:
        key = (f.get("author"), f.get("body"))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)

    print(f"actionable_count={len(uniq)}")
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f:
            json.dump({"pr": pr_num, "pr_url": pr_url, "actionable": uniq}, f, indent=2)
    if args.md_path:
        with open(args.md_path, "w", encoding="utf-8") as f:
            f.write(f"# PR #{pr_num} review summary\n\n")
            if not uniq:
                f.write("- No actionable comments found\n")
            else:
                for i, item in enumerate(uniq, start=1):
                    f.write(f"{i}. {item['author']} ({item['source']}): {item['body']}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
