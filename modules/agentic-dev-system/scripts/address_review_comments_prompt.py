#!/usr/bin/env python3
"""Generate a scoped Codex prompt from collected PR review comments."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


MUST_FIX_TERMS = [
    "must",
    "required",
    "blocker",
    "broken",
    "incorrect",
    "security",
    "regression",
    "missing test",
    "failing",
]
SHOULD_FIX_TERMS = ["should", "please", "need", "fix", "change", "requested"]
CLARIFY_TERMS = ["clarify", "unclear", "question", "?"]


def load_payload(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify(body: str) -> str:
    text = body.lower()
    if any(term in text for term in MUST_FIX_TERMS):
        return "must_fix"
    if any(term in text for term in CLARIFY_TERMS):
        return "clarify"
    if any(term in text for term in SHOULD_FIX_TERMS):
        return "should_fix"
    return "note"


def normalize_items(payload: dict) -> list[dict]:
    out = []
    for idx, item in enumerate(payload.get("actionable", []), start=1):
        body = (item.get("body") or "").strip()
        if not body:
            continue
        out.append(
            {
                "id": idx,
                "classification": classify(body),
                "source": item.get("source", "unknown"),
                "author": item.get("author", "unknown"),
                "url": item.get("url", ""),
                "body": body,
            }
        )
    return out


def summarize(payload: dict, items: list[dict]) -> dict:
    counts = {"must_fix": 0, "should_fix": 0, "clarify": 0, "note": 0}
    for item in items:
        counts[item["classification"]] += 1
    return {
        "pr": payload.get("pr"),
        "pr_url": payload.get("pr_url"),
        "counts": counts,
        "items": items,
    }


def render_section(title: str, items: list[dict]) -> list[str]:
    lines = [f"## {title}"]
    if not items:
        lines.append("- None")
        return lines
    for item in items:
        url = f" ({item['url']})" if item.get("url") else ""
        lines.append(f"{item['id']}. {item['author']} [{item['source']}]{url}: {item['body']}")
    return lines


def render_prompt(summary: dict) -> str:
    by_class = {
        kind: [item for item in summary["items"] if item["classification"] == kind]
        for kind in ("must_fix", "should_fix", "clarify", "note")
    }
    lines = [
        "# Address PR Review Comments",
        "",
        f"PR: {summary.get('pr') or 'unknown'}",
    ]
    if summary.get("pr_url"):
        lines.append(f"URL: {summary['pr_url']}")
    lines.extend(
        [
            "",
            "Use superpowers:receiving-code-review before applying feedback.",
            "",
            "Fix only in-scope must-fix and should-fix review comments.",
            "Do not broaden scope.",
            "Do not address clarify-only items until the ambiguity is resolved.",
            "Run verification.",
            "Commit and push follow-up changes.",
            "Reply with evidence.",
            "Do not mark unresolved comments resolved unless actually addressed.",
            "",
        ]
    )
    lines.extend(render_section("Must Fix", by_class["must_fix"]))
    lines.append("")
    lines.extend(render_section("Should Fix", by_class["should_fix"]))
    lines.append("")
    lines.extend(render_section("Needs Clarification", by_class["clarify"]))
    lines.append("")
    lines.extend(render_section("Notes", by_class["note"]))
    lines.append("")
    lines.extend(
        [
            "## Required Completion Note",
            "- Files changed",
            "- Review comments addressed",
            "- Verification commands and results",
            "- Comments replied to with evidence",
            "- Remaining risks or unresolved clarifications",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="JSON output from request_review_and_poll.py")
    parser.add_argument("--output", help="Markdown prompt output path")
    parser.add_argument("--json-output", help="Actionable review summary JSON output path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = load_payload(Path(args.input).expanduser())
    items = normalize_items(payload)
    summary = summarize(payload, items)
    prompt = render_prompt(summary)

    if args.dry_run:
        if args.output:
            print(f"DRY-RUN: would write prompt to {args.output}")
        if args.json_output:
            print(f"DRY-RUN: would write summary to {args.json_output}")
        print(prompt)
        return 0

    if args.output:
        Path(args.output).expanduser().write_text(prompt, encoding="utf-8")
        print(f"WROTE: {args.output}")
    else:
        print(prompt)

    if args.json_output:
        Path(args.json_output).expanduser().write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"WROTE: {args.json_output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
