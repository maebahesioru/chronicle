"""Dataclasses shared by every stage of the Chronicle pipeline."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CONVENTIONAL_TYPES = (
    "feat",
    "fix",
    "docs",
    "test",
    "refactor",
    "perf",
    "chore",
    "build",
    "ci",
    "style",
    "revert",
)

CONV_RE = re.compile(
    r"^(?P<type>[a-zA-Z]+)(?:\((?P<scope>[^()]*)\))?(?P<bang>!)?: (?P<subject>.+)$"
)
ISSUE_RE = re.compile(r"#(\d{1,6})\b")


@dataclass
class FileChange:
    path: str
    added: int = 0
    deleted: int = 0
    binary: bool = False

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "added": self.added,
            "deleted": self.deleted,
            "binary": self.binary,
        }


def parse_conventional(subject: str) -> tuple[str | None, str | None]:
    """Return (type, scope) for a conventional-commit subject, else (None, None)."""
    match = CONV_RE.match(subject.strip())
    if not match:
        return None, None
    ctype = match.group("type").lower()
    if ctype not in CONVENTIONAL_TYPES:
        return None, None
    scope = (match.group("scope") or "").strip() or None
    return ctype, scope


@dataclass
class Commit:
    sha: str
    short: str
    author: str
    date: str
    subject: str
    body: str = ""
    files: list[FileChange] = field(default_factory=list)
    ctype: str | None = None
    scope: str | None = None
    issue_refs: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.ctype is None and self.scope is None:
            self.ctype, self.scope = parse_conventional(self.subject)
        if not self.issue_refs:
            self.issue_refs = extract_issue_refs(self.subject + "\n" + self.body)

    @property
    def added(self) -> int:
        return sum(f.added for f in self.files)

    @property
    def deleted(self) -> int:
        return sum(f.deleted for f in self.files)

    def to_dict(self) -> dict:
        return {
            "sha": self.sha,
            "short": self.short,
            "author": self.author,
            "date": self.date,
            "subject": self.subject,
            "body": self.body,
            "ctype": self.ctype,
            "scope": self.scope,
            "issue_refs": list(self.issue_refs),
            "files": [f.to_dict() for f in self.files],
        }


def extract_issue_refs(text: str) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for match in ISSUE_RE.finditer(text or ""):
        value = int(match.group(1))
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


@dataclass
class Chapter:
    """A chronological bundle of commits that tell one part of the story."""

    index: int
    commits: list[Commit]

    def __post_init__(self) -> None:
        self.files_by_path: dict[str, dict[str, int]] = {}
        for commit in self.commits:
            for change in commit.files:
                entry = self.files_by_path.setdefault(
                    change.path, {"added": 0, "deleted": 0, "commits": 0}
                )
                entry["added"] += change.added
                entry["deleted"] += change.deleted
                entry["commits"] += 1

    @property
    def kind(self) -> str:
        counts: dict[str, int] = {}
        for commit in self.commits:
            if commit.ctype:
                counts[commit.ctype] = counts.get(commit.ctype, 0) + 1
        if not counts:
            return "other"
        best = max(counts.items(), key=lambda item: (item[1], -CONVENTIONAL_TYPES.index(item[0]) if item[0] in CONVENTIONAL_TYPES else 99))
        return best[0]

    @property
    def scope(self) -> str | None:
        counts: dict[str, int] = {}
        for commit in self.commits:
            if commit.scope:
                counts[commit.scope] = counts.get(commit.scope, 0) + 1
        if not counts:
            return None
        top = max(counts.values())
        winners = sorted(name for name, count in counts.items() if count == top)
        return winners[0]

    @property
    def files(self) -> list[FileChange]:
        out = [
            FileChange(path=path, added=stats["added"], deleted=stats["deleted"])
            for path, stats in sorted(self.files_by_path.items())
        ]
        return out

    @property
    def paths(self) -> list[str]:
        return sorted(self.files_by_path)

    @property
    def added(self) -> int:
        return sum(stats["added"] for stats in self.files_by_path.values())

    @property
    def deleted(self) -> int:
        return sum(stats["deleted"] for stats in self.files_by_path.values())

    @property
    def start(self) -> str:
        return self.commits[0].date

    @property
    def end(self) -> str:
        return self.commits[-1].date

    @property
    def title(self) -> str:
        scope = self.scope
        if scope:
            return f"{self.kind}({scope})"
        paths = self.paths
        if paths:
            top = sorted(
                {p.split("/")[0] for p in paths if "/" in p} or {p for p in paths}
            )
            area = top[0]
            if len(top) > 1:
                area = f"{area} +{len(top) - 1}"
            return f"{self.kind}: {area}"
        return self.kind

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "title": self.title,
            "kind": self.kind,
            "scope": self.scope,
            "start": self.start,
            "end": self.end,
            "added": self.added,
            "deleted": self.deleted,
            "paths": self.paths,
            "commits": [c.to_dict() for c in self.commits],
        }
