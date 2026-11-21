"""Shared fixtures: tiny throwaway git repositories."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

NL = chr(10)


def lines(*parts: str) -> str:
    return NL.join(parts) + NL


def run_git(repo: Path, *args: str, env: dict | None = None) -> str:
    merged = {
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test Author",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "HOME": str(repo.parent),
    }
    if env:
        merged.update(env)
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env={**os.environ, **merged},
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), result.stderr))
    return result.stdout


def write_file(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def commit(repo: Path, message: str, date: str = "2026-11-21T10:00:00+09:00") -> str:
    run_git(repo, "add", "-A")
    run_git(
        repo,
        "commit",
        "-m",
        message,
        env={"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date},
    )
    return run_git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "Test Author")

    write_file(repo, "src/core/parser.py", lines("def parse(x):", "    return x"))
    commit(repo, "feat(parser): add the first parser", "2026-11-21T10:00:00+09:00")

    write_file(repo, "src/core/parser.py", lines("def parse(x):", "    return x.strip()"))
    commit(repo, "fix(parser): strip whitespace before parsing", "2026-11-22T10:00:00+09:00")

    write_file(repo, "src/core/render.py", lines("def render(x):", "    return str(x)"))
    write_file(repo, "src/core/parser.py", lines("def parse(x):", "    return x.strip().lower()"))
    commit(repo, "feat(parser): normalise case after stripping", "2026-11-23T10:00:00+09:00")

    write_file(repo, "docs/guide.md", lines("# Guide", ""))
    commit(repo, "docs: explain how parsing works", "2026-11-24T10:00:00+09:00")

    write_file(repo, "src/core/render.py", lines("def render(x):", "    return str(x) + '!'"))
    commit(repo, "tighten rendering output", "2026-11-25T10:00:00+09:00")

    write_file(repo, "src/core/render.py", lines("def render(x):", "    return str(x) + '?'"))
    write_file(repo, "src/core/parser.py", lines("def parse(x):", "    return x.strip().lower()", "# done"))
    commit(repo, "clean up renderer edge case", "2026-11-26T10:00:00+09:00")

    run_git(repo, "tag", "v0.1.0", "HEAD~2")
    return repo
