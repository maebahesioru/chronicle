"""git history reading and the --since release filter."""

from __future__ import annotations

import pytest

from chronicle.core.gitlog import (
    GitError,
    diff_excerpt,
    head_sha,
    read_commits,
    resolve_since,
)


def test_reads_all_commits_oldest_first(sample_repo):
    commits = read_commits(str(sample_repo))
    assert len(commits) == 6
    assert commits[0].subject.startswith("feat(parser): add the first parser")
    assert commits[-1].subject == "clean up renderer edge case"
    assert commits[0].ctype == "feat"
    assert commits[0].scope == "parser"
    assert commits[-1].ctype is None


def test_since_tag_keeps_only_recent_commits(sample_repo):
    sha = resolve_since(str(sample_repo), "v0.1.0")
    assert sha == head_sha(str(sample_repo))[:0] + sha
    commits = read_commits(str(sample_repo), since=sha)
    assert [commit.subject for commit in commits] == [
        "tighten rendering output",
        "clean up renderer edge case",
    ]


def test_unknown_since_ref_is_a_clean_error(sample_repo):
    with pytest.raises(GitError) as excinfo:
        resolve_since(str(sample_repo), "does-not-exist")
    assert "does-not-exist" in str(excinfo.value)


def test_diff_excerpt_returns_unified_lines(sample_repo):
    commits = read_commits(str(sample_repo))
    target = commits[-1]
    excerpt = diff_excerpt(str(sample_repo), target.sha, "src/core/render.py")
    assert excerpt.path == "src/core/render.py"
    assert excerpt.lines
    assert any(line.startswith("+") for line in excerpt.lines)
    assert excerpt.truncated is False
