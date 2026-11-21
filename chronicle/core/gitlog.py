"""Read a git repository's history with the git CLI only (no third-party deps)."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

from .model import Commit, FileChange


class GitError(RuntimeError):
    """Raised when git cannot answer a question about the repository."""


def _run_git(repo: str, args: list[str], timeout: int = 60) -> str:
    env = dict(os.environ)
    env.setdefault("GIT_OPTIONAL_LOCKS", "0")
    env.setdefault("LC_ALL", "C.UTF-8")
    try:
        proc = subprocess.run(
            ["git", "-C", repo, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:  # pragma: no cover - git missing
        raise GitError("git executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git timed out after %ss: %s" % (timeout, " ".join(args))) from exc
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise GitError("git %s failed: %s" % (" ".join(args), detail))
    return proc.stdout


def is_git_repo(repo: str) -> bool:
    if not os.path.isdir(repo):
        return False
    try:
        _run_git(repo, ["rev-parse", "--is-inside-work-tree"], timeout=15)
        return True
    except GitError:
        return False


def repo_root(repo: str) -> str:
    return _run_git(repo, ["rev-parse", "--show-toplevel"], timeout=15).strip()


def repo_name(repo: str) -> str:
    root = repo_root(repo)
    return os.path.basename(root.rstrip("/")) or root


def head_sha(repo: str) -> str:
    return _run_git(repo, ["rev-parse", "HEAD"], timeout=15).strip()


def resolve_since(repo: str, since: str) -> str:
    """Resolve a tag/ref/sha to a full commit SHA; raise GitError if unknown."""
    try:
        out = _run_git(
            repo, ["rev-parse", "--verify", "--quiet", since + "^{commit}"], timeout=15
        )
    except GitError as exc:
        raise GitError("unknown --since ref %r: %s" % (since, exc)) from exc
    sha = out.strip()
    if not sha:
        raise GitError("unknown --since ref %r" % (since,))
    return sha


def _split_records(text: str) -> list[str]:
    return [chunk for chunk in text.split("\x1e") if chunk.strip()]


def _parse_metadata(text: str) -> list[tuple[str, str, str, str, str]]:
    rows = []
    for record in _split_records(text):
        fields = record.split("\x1f")
        if len(fields) < 5:
            continue
        sha = fields[0].strip()
        date = fields[1].strip()
        author = fields[2].strip()
        subject = fields[3].strip()
        body = "\x1f".join(fields[4:]).strip()
        rows.append((sha, date, author, subject, body))
    return rows


def _parse_numstat(text: str) -> dict[str, list[FileChange]]:
    result: dict[str, list[FileChange]] = {}
    current = None
    for line in text.splitlines():
        if not line:
            continue
        if line.startswith("\x01"):
            current = line[1:].strip()
            result.setdefault(current, [])
            continue
        if current is None:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        added_raw, deleted_raw, path = parts[0], parts[1], "\t".join(parts[2:])
        binary = added_raw == "-" or deleted_raw == "-"
        added = 0 if binary else int(added_raw)
        deleted = 0 if binary else int(deleted_raw)
        path = path.strip()
        if " => " in path:  # --no-renames keeps this rare, but keep a sane fallback
            path = path.split(" => ")[-1].strip("{} ").strip()
        result[current].append(
            FileChange(path=path, added=added, deleted=deleted, binary=binary)
        )
    return result


def read_commits(repo: str, since: str | None = None) -> list[Commit]:
    """Return commits oldest-first, merge commits excluded.

    The since argument may be a tag, branch, or SHA. The returned range is
    since..HEAD so release mode only narrates new work.
    """
    if not is_git_repo(repo):
        raise GitError("not a git repository: %s" % repo)

    revision = "HEAD"
    if since:
        base_sha = resolve_since(repo, since)
        revision = base_sha + "..HEAD"

    meta = _run_git(
        repo,
        [
            "log",
            "--reverse",
            "--no-merges",
            "--no-renames",
            "--date=iso-strict",
            "--format=%H%x1f%aI%x1f%an%x1f%s%x1f%b%x1e",
            revision,
        ],
    )
    numstat = _run_git(
        repo,
        [
            "log",
            "--reverse",
            "--no-merges",
            "--no-renames",
            "--format=%x01%H",
            "--numstat",
            revision,
        ],
    )
    changes = _parse_numstat(numstat)
    commits: list[Commit] = []
    for sha, date, author, subject, body in _parse_metadata(meta):
        commits.append(
            Commit(
                sha=sha,
                short=sha[:7],
                author=author,
                date=date,
                subject=subject,
                body=body,
                files=changes.get(sha, []),
            )
        )
    return commits


@dataclass
class DiffExcerpt:
    path: str
    sha: str
    lines: list[str]
    truncated: bool = False


def diff_excerpt(
    repo: str, sha: str, path: str, max_lines: int = 48, timeout: int = 30
) -> DiffExcerpt | None:
    """Return a small, colour-free diff hunk for one commit/file pair."""
    try:
        raw = _run_git(
            repo,
            [
                "show",
                "--format=",
                "--no-color",
                "--no-ext-diff",
                "--unified=1",
                sha,
                "--",
                path,
            ],
            timeout=timeout,
        )
    except GitError:
        return None
    lines = [line for line in raw.splitlines() if not line.startswith("\\ ")]
    if not lines:
        return None
    truncated = len(lines) > max_lines
    return DiffExcerpt(path=path, sha=sha, lines=lines[:max_lines], truncated=truncated)
