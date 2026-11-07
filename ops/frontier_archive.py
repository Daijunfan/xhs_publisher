#!/usr/bin/env python3
"""Synchronize reviewed Mac source and commit only its explicit file scope.

The current branch is retained. Credentials, runtime state, other Toolbox tools,
and pre-existing staged files outside the reviewed scope are never added.
This helper does not push or initialize repositories.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def git(repo, *arguments, check=True):
    return subprocess.run(["git", "-C", str(repo), *arguments], check=check, capture_output=True)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise RuntimeError("A reviewed manifest must be a JSON object")
    return data


def safe_name(name):
    return isinstance(name, str) and bool(name) and not Path(name).is_absolute() and ".." not in Path(name).parts


def repository(repo, expected_head=None, expected_branch=None):
    repo = repo.resolve()
    top = Path(git(repo, "rev-parse", "--show-toplevel").stdout.decode().strip()).resolve()
    if top != repo:
        raise RuntimeError("The selected directory is not the repository root")
    head = git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    branch = git(repo, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.decode().strip()
    if expected_head:
        expected = git(repo, "rev-parse", "--verify", expected_head + "^{commit}").stdout.decode().strip()
        if head != expected:
            raise RuntimeError("The Mac repository HEAD changed since review")
    if expected_branch and branch != expected_branch:
        raise RuntimeError("The Mac repository branch changed since review")
    return repo, head, branch


def blob(repo, revision, name):
    response = git(repo, "show", revision + ":" + name, check=False)
    return response.stdout if response.returncode == 0 else None


def tracked(repo, prefix):
    value = git(repo, "ls-files", "-z", "--", prefix).stdout
    return [path.decode() for path in value.split(b"\0") if path]


def outside_staged(repo, scope):
    names = [p.decode() for p in git(repo, "diff", "--cached", "--name-only", "-z").stdout.split(b"\0") if p]
    outside = [name for name in names if name not in scope]
    content = git(repo, "diff", "--cached", "--binary", "--", *outside).stdout if outside else b""
    return {"count": len(outside), "sha256": digest(content)}


def check_destination(repo, head, name, incoming):
    if not safe_name(name):
        raise RuntimeError("Manifest contains an unsafe relative path")
    path = repo / name
    if not path.resolve().is_relative_to(repo):
        raise RuntimeError("A destination resolves outside the repository")
    if path.exists() and not path.is_file():
        raise RuntimeError("A file destination is occupied by another kind of entry: " + name)
    old = blob(repo, head, name)
    current = path.read_bytes() if path.exists() else None
    if current not in (old, incoming):
        raise RuntimeError("A reviewed source file has unrelated local changes: " + name)
    staged = blob(repo, "", name)
    if staged not in (old, incoming):
        raise RuntimeError("A reviewed source file has unrelated staged changes: " + name)


def write_plan(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2))
    temporary.chmod(0o600)
    temporary.replace(path)


def make_plan(args, incoming, *, write):
    repo, head, branch = repository(args.repo, args.expected_head, args.expected_branch)
    for name, content in incoming.items():
        check_destination(repo, head, name, content)
    if not write:
        for name, content in incoming.items():
            path = repo / name
            if not path.is_file() or path.read_bytes() != content:
                raise RuntimeError("The reviewed native source is not installed exactly: " + name)
    scope = set(incoming)
    staged_before = outside_staged(repo, scope)
    backup = None
    if write:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup = repo / "runtime/frontier-v2-source-backups" / stamp
        backup.mkdir(parents=True, mode=0o700)
        existed = {}
        for name in incoming:
            source = repo / name
            existed[name] = source.exists()
            if source.exists():
                target = backup / "files" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        write_plan(backup / "scope.json", {"head": head, "branch": branch, "existed": existed})
        try:
            for name, content in incoming.items():
                path = repo / name
                if content is None:
                    path.unlink(missing_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_name("." + path.name + ".frontier-sync")
                temporary.write_bytes(content)
                if path.is_file():
                    temporary.chmod(path.stat().st_mode & 0o777)
                temporary.replace(path)
        except BaseException:
            for name, previous in existed.items():
                path = repo / name
                if previous:
                    shutil.copy2(backup / "files" / name, path)
                else:
                    path.unlink(missing_ok=True)
            raise
    git_scope = []
    for name in incoming:
        ignored = git(repo, "check-ignore", "--quiet", "--", name, check=False).returncode == 0
        if ignored and not name.startswith("src/xhs_local/frontier/static/"):
            raise RuntimeError("A reviewed source file is unexpectedly ignored by Git: " + name)
        if not ignored:
            git_scope.append(name)
    if outside_staged(repo, scope) != staged_before:
        raise RuntimeError("Staged content outside the source scope changed; review before committing")
    plan = {"kind": "frontier-reviewed-git-scope", "repo": str(repo), "head": head, "branch": branch,
            "files": {name: digest(content) if content is not None else None for name, content in incoming.items()},
            "git_scope": sorted(git_scope), "outside_staged": staged_before, "backup": str(backup) if backup else None}
    write_plan(args.plan, plan)
    print(json.dumps({"review_plan": str(args.plan), "branch": branch, "head": head,
                      "source_files": len(incoming), "git_scope": sorted(git_scope),
                      "unrelated_staged_preserved": staged_before["count"], "committed": False, "pushed": False}, ensure_ascii=False))


def sync_xhs(args):
    manifest = read_json(args.backend_manifest)
    incoming = {}
    for name, entry in manifest["files"].items():
        if not safe_name(name) or not (name.startswith(("src/", "tests/", "ops/")) or name in {"pyproject.toml", "uv.lock", "FRONTIER_V2.md"}):
            raise RuntimeError("Backend manifest path is outside the Xhs source scope")
        data = entry["content"].encode()
        if digest(data) != entry["sha256"]:
            raise RuntimeError("Backend manifest checksum mismatch")
        incoming[name] = data
    for name, contents in read_json(args.frontend_manifest).items():
        if not safe_name(name) or not isinstance(contents, str):
            raise RuntimeError("Invalid frontend manifest entry")
        incoming["frontend/" + name] = contents.encode()
    static = args.static.resolve()
    if not (static / "index.html").is_file():
        raise RuntimeError("The reviewed built frontend index is missing")
    for path in static.rglob("*"):
        if path.is_symlink():
            raise RuntimeError("The reviewed static directory must not contain symlinks")
        if path.is_file():
            incoming["src/xhs_local/frontier/static/" + path.relative_to(static).as_posix()] = path.read_bytes()
    for name in tracked(args.repo, "src/xhs_local/frontier/static"):
        if name not in incoming:
            incoming[name] = None
    make_plan(args, incoming, write=True)


def plan_toolbox(args):
    incoming = {}
    for name, contents in read_json(args.native_manifest).items():
        if not safe_name(name) or not isinstance(contents, str):
            raise RuntimeError("Invalid native manifest entry")
        incoming["Frontier/" + name] = contents.encode()
    make_plan(args, incoming, write=False)


def commit(args):
    plan = read_json(args.plan)
    if plan.get("kind") != "frontier-reviewed-git-scope":
        raise RuntimeError("The input is not a reviewed Git scope plan")
    repo, _head, _branch = repository(Path(plan["repo"]), plan["head"], plan["branch"])
    scope = set(plan["files"])
    if not set(plan["git_scope"]) <= scope or any(not safe_name(name) for name in scope):
        raise RuntimeError("The Git scope plan contains an invalid path")
    for name, expected in plan["files"].items():
        path = repo / name
        actual = digest(path.read_bytes()) if path.is_file() else None
        if actual != expected:
            raise RuntimeError("A reviewed source changed after the plan was produced: " + name)
    if outside_staged(repo, scope) != plan["outside_staged"]:
        raise RuntimeError("Unrelated staged state changed after review; refresh the plan")
    paths = plan["git_scope"]
    if not paths:
        raise RuntimeError("The plan has no version-controlled source changes")
    git(repo, "add", "-A", "--", *paths)
    if git(repo, "diff", "--cached", "--quiet", "--", *paths, check=False).returncode == 0:
        print(json.dumps({"committed": False, "reason": "Reviewed source already matches HEAD", "pushed": False}))
        return
    descriptor, temporary = tempfile.mkstemp(prefix="frontier-commit-", suffix=".txt", dir=args.plan.parent)
    try:
        with os.fdopen(descriptor, "w") as body:
            body.write(args.message.rstrip() + "\n")
        git(repo, "commit", "--only", "--file", temporary, "--", *paths)
    finally:
        Path(temporary).unlink(missing_ok=True)
    changed = {value.decode() for value in git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "HEAD").stdout.split(b"\0") if value}
    if not changed <= set(paths) or outside_staged(repo, scope) != plan["outside_staged"]:
        raise RuntimeError("The commit scope or preserved staged content did not match the review plan")
    head = git(repo, "rev-parse", "HEAD").stdout.decode().strip()
    print(json.dumps({"committed": True, "head": head, "files": sorted(changed),
                      "unrelated_staged_preserved": plan["outside_staged"]["count"], "pushed": False}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["sync-xhs", "plan-toolbox", "commit"])
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--expected-head")
    parser.add_argument("--expected-branch")
    parser.add_argument("--backend-manifest", type=Path)
    parser.add_argument("--frontend-manifest", type=Path)
    parser.add_argument("--native-manifest", type=Path)
    parser.add_argument("--static", type=Path)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--message")
    args = parser.parse_args()
    requirements = {"sync-xhs": ("repo", "expected_head", "expected_branch", "backend_manifest", "frontend_manifest", "static"),
                    "plan-toolbox": ("repo", "native_manifest"), "commit": ("message",)}
    for name in requirements[args.action]:
        if getattr(args, name) is None:
            parser.error("--" + name.replace("_", "-") + " is required")
    {"sync-xhs": sync_xhs, "plan-toolbox": plan_toolbox, "commit": commit}[args.action](args)


if __name__ == "__main__":
    main()
