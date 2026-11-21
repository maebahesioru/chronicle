"""Turn a flat commit list into chronological chapters.

Two signals decide the grouping, in this order:

1. Conventional commit type (and scope, when present). Every feat commit
   belongs to the feat chapter, every fix to the fix chapter, and so on.
2. File-set similarity for commits that do not follow the convention. A
   commit joins the earliest earlier cluster whose path set overlaps enough
   (Jaccard) and starts a new cluster otherwise.

The pass is deterministic: input order is the git log order (oldest first)
and every tie is broken by first appearance, never by hashing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Chapter, Commit

DEFAULT_SIMILARITY = 0.34
DEFAULT_MAX_COMMITS = 8


def top_dir(path: str) -> str:
    """Return the first path segment, or the bare filename for a root file."""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return path
    if len(parts) == 1:
        return parts[0]
    return parts[0]


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


@dataclass
class _Group:
    commits: list[Commit] = field(default_factory=list)
    paths: set[str] = field(default_factory=set)
    ctype: str | None = None
    scope: str | None = None
    order: int = 0

    def add(self, commit: Commit) -> None:
        self.commits.append(commit)
        for change in commit.files:
            self.paths.add(change.path)


def _conventional_key(commit: Commit) -> tuple[str, str | None] | None:
    if not commit.ctype:
        return None
    return commit.ctype, commit.scope


def group_commits(
    commits: list[Commit],
    similarity: float = DEFAULT_SIMILARITY,
) -> list[list[Commit]]:
    """Group commits into narrative buckets, returned in first-seen order."""
    groups: list[_Group] = []
    for position, commit in enumerate(commits):
        paths = {change.path for change in commit.files}
        key = _conventional_key(commit)
        chosen: _Group | None = None

        if key is not None:
            ctype, scope = key
            for group in groups:
                if group.ctype != ctype:
                    continue
                same_scope = group.scope == scope
                open_scope = group.scope is None or scope is None
                if same_scope or open_scope:
                    chosen = group
                    break
        else:
            best_score = 0.0
            for group in groups:
                if group.ctype is not None:
                    continue
                score = jaccard(paths, group.paths)
                if score > best_score:
                    best_score = score
                    chosen = group
            if best_score < similarity:
                chosen = None

        if chosen is None:
            chosen = _Group(order=len(groups))
            if key is not None:
                chosen.ctype, chosen.scope = key
            groups.append(chosen)
        chosen.add(commit)

    return [list(group.commits) for group in groups]


def build_chapters(
    commits: list[Commit],
    similarity: float = DEFAULT_SIMILARITY,
    max_commits: int = DEFAULT_MAX_COMMITS,
) -> list[Chapter]:
    """Cluster commits and split oversized buckets into readable chapters."""
    if not commits:
        return []

    chapters: list[Chapter] = []
    for bucket in group_commits(commits, similarity=similarity):
        size = max(1, int(max_commits))
        chunks = [bucket[i : i + size] for i in range(0, len(bucket), size)]
        for chunk in chunks:
            chapters.append(Chapter(index=len(chapters) + 1, commits=chunk))
    return chapters
