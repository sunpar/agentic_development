#!/usr/bin/env python3
"""Detect repository context for planning artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def first_existing(root: Path, names):
    for name in names:
        p = root / name
        if p.exists():
            return p
    return None


def pkg_manager(root: Path):
    checks = [
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("package-lock.json", "npm"),
        ("requirements.txt", "pip"),
        ("poetry.lock", "poetry"),
        ("pyproject.toml", "python"),
        ("go.mod", "go"),
        ("Cargo.toml", "cargo"),
    ]
    for fname, mgr in checks:
        if (root / fname).exists():
            return mgr
    return "unknown"


def package_files(root: Path):
    return [p.name for p in root.iterdir() if p.name in {"package.json", "requirements.txt", "pyproject.toml", "go.mod", "Cargo.toml"}]


def test_commands(root: Path):
    package_json = root / "package.json"
    cmds = {}
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            scripts = data.get("scripts", {})
            cmds["build"] = scripts.get("build", "npm run build")
            cmds["test"] = scripts.get("test", "npm test")
            cmds["lint"] = scripts.get("lint", "npm run lint")
        except Exception:
            pass
    if (root / "pyproject.toml").exists():
        cmds.setdefault("test", "pytest")
        cmds.setdefault("lint", "ruff check .")
    if (root / "go.mod").exists():
        cmds.setdefault("build", "go build ./...")
        cmds.setdefault("test", "go test ./...")
    return cmds


def ci_files(root: Path):
    cands = [
        ".github/workflows",
        "bitbucket-pipelines.yml",
        ".gitlab-ci.yml",
        "CircleCI/config.yml",
        "azure-pipelines.yml",
    ]
    found = []
    for c in cands:
        p = root / c
        if p.exists():
            if p.is_dir():
                found.extend(str(x.relative_to(root)) for x in p.iterdir())
            else:
                found.append(c)
    return sorted(set(found))


def source_dirs(root: Path):
    top = [p.name for p in root.iterdir() if p.is_dir() and p.name in {"src", "app", "lib", "server", "client", "backend", "frontend"}]
    return sorted(top)

def test_dirs(root: Path):
    top = [p.name for p in root.iterdir() if p.is_dir() and p.name in {"tests", "test", "__tests__", "spec"}]
    return sorted(top)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default='.')
    parser.add_argument("--out", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    root = Path(args.repo).expanduser().resolve()
    if not (root / '.git').exists():
        print(f"ERROR: {root} is not a git repo")
        return 2

    payload = {
        "repository": str(root),
        "package_manager": pkg_manager(root),
        "package_files": package_files(root),
        "test_commands": test_commands(root),
        "ci_files": ci_files(root),
        "source_dirs": source_dirs(root),
        "test_dirs": test_dirs(root),
    }
    lines = [
        "# repo context map",
        f"- repository: {payload['repository']}",
        f"- package_manager: {payload['package_manager']}",
        f"- package_files: {', '.join(payload['package_files']) or '(none)'}",
        f"- source_dirs: {', '.join(payload['source_dirs']) or '(none)'}",
        f"- test_dirs: {', '.join(payload['test_dirs']) or '(none)'}",
        "\n## CI",
    ]
    lines.extend([f"- {x}" for x in payload['ci_files'] or ["(none)"]])
    lines.append("\n## Test and Build")
    for k, v in payload['test_commands'].items():
        lines.append(f"- {k}: `{v}`")

    out = "\n".join(lines)
    if args.out and args.dry_run:
        print(f"DRY-RUN: would write repo context artifacts to {args.out}")
        print(out)
    elif args.out:
        out_dir = Path(args.out).expanduser()
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "repo-map.md").open("w", encoding="utf-8") as f:
            f.write(out)
        with (out_dir / "test-commands.md").open("w", encoding="utf-8") as f:
            f.write("\n".join([f"- {k}: `{v}`" for k, v in payload["test_commands"].items()]))
        with (out_dir / "architecture-index.md").open("w", encoding="utf-8") as f:
            f.write("# architecture index\n")
            for d in payload["source_dirs"]:
                f.write(f"- {d}\n")
    else:
        print(out)

    print("repo context generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
