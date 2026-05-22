#!/usr/bin/env python3
import argparse
import json
import os
import re
import shlex
import sys

DANGEROUS = [
    r"\brm\s+(-[a-zA-Z]*\s+)?-rf\b",
    r"\bchmod\s+[^\n]*-R\b",
    r"\bgit\s+reset\s+--hard\b",
    r"\bgit\s+clean\s+-fdx\b",
    r"\bgh\s+(repo\s+delete|api\s+api|auth\s+logout)\b",
    r"\bterraform\s+destroy\b",
]


def is_strict():
    return os.environ.get("AGENTIC_DEV_STRICT_HOOKS", "0") == "1"


def parse_hook_json(raw):
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def get_command_text(args):
    if args.command:
        return " ".join(args.command)
    raw = sys.stdin.read().strip()
    payload = parse_hook_json(raw)
    if payload:
        tool_input = payload.get("tool_input")
        if isinstance(tool_input, dict) and isinstance(tool_input.get("command"), str):
            return tool_input["command"]
        if isinstance(payload.get("command"), str):
            return payload["command"]
    return raw


def main(argv=None):
    parser = argparse.ArgumentParser(description="Warn or block risky shell tool commands.")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Command text to inspect; stdin is used when omitted.")
    args = parser.parse_args(argv)

    cmd = get_command_text(args).strip()
    if not cmd:
        return 0
    lowered = cmd.lower()
    for pat in DANGEROUS:
        if re.search(pat, lowered):
            msg = f"dangerous command pattern: {pat}"
            if is_strict():
                print(f"tool_policy blocked: {msg} command={shlex.quote(cmd[:120])}")
                return 2
            print(f"tool_policy warning: {msg}")
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
