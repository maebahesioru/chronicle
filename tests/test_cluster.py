"""Clustering is deterministic and respects conventional commit types."""

from __future__ import annotations

from chronicle.core.cluster import build_chapters, group_commits, jaccard
from chronicle.core.model import FileChange, Commit


def make_commit(sha: str, subject: str, paths: list[str]) -> Commit:
    return Commit(
        sha=sha * 40 if len(sha) < 40 else sha,
        short=sha[:7],
        author="Test",
        date="2026-11-21T10:00:00+09:00",
        subject=subject,
        files=[FileChange(path=path, added=1, deleted=0) for path in paths],
    )


def test_jaccard_bounds():
    assert jaccard(set(), set()) == 0.0
    assert jaccard({"a"}, {"a"}) == 1.0
    assert jaccard({"a"}, {"b"}) == 0.0


def test_conventional_commits_with_same_type_and_scope_join():
    commits = [
        make_commit("aaaaaaa1", "feat(parser): add parser", ["src/parser.py"]),
        make_commit("aaaaaaa2", "feat(parser): extend parser", ["src/parser.py"]),
        make_commit("aaaaaaa3", "docs: write guide", ["docs/guide.md"]),
    ]
    groups = group_commits(commits)
    assert [len(group) for group in groups] == [2, 1]


def test_uncategorised_commits_join_by_file_overlap():
    commits = [
        make_commit("bbbbbbb1", "tighten the parser", ["src/parser.py", "src/util.py"]),
        make_commit("bbbbbbb2", "clean parser edge case", ["src/parser.py"]),
        make_commit("bbbbbbb3", "unrelated notes", ["notes/todo.md"]),
    ]
    groups = group_commits(commits)
    assert [len(group) for group in groups] == [2, 1]


def test_clustering_is_deterministic():
    commits = [
        make_commit("ccccccc1", "feat(api): add endpoint", ["src/api.py"]),
        make_commit("ccccccc2", "fix(api): repair endpoint", ["src/api.py"]),
        make_commit("ccccccc3", "misc tweak", ["src/ui.py"]),
        make_commit("ccccccc4", "another tweak", ["src/ui.py"]),
    ]
    a = [tuple(commit.sha for commit in chapter.commits) for chapter in build_chapters(commits)]
    b = [tuple(commit.sha for commit in chapter.commits) for chapter in build_chapters(commits)]
    assert a == b
    assert [len(group) for group in a] == [1, 1, 2]


def test_max_commits_splits_long_groups_and_indexes_from_one():
    commits = [
        make_commit("ddddddd%d" % index, "feat(core): change %d" % index, ["src/core.py"])
        for index in range(1, 6)
    ]
    chapters = build_chapters(commits, max_commits=2)
    assert [chapter.index for chapter in chapters] == [1, 2, 3]
    assert [len(chapter.commits) for chapter in chapters] == [2, 2, 1]


def test_chapter_aggregates_files_and_stats():
    commits = [
        make_commit("eeeeeee1", "feat(core): one", ["src/core.py"]),
        make_commit("eeeeeee2", "feat(core): two", ["src/core.py", "docs/x.md"]),
    ]
    chapter = build_chapters(commits)[0]
    assert chapter.paths == ["docs/x.md", "src/core.py"]
    assert chapter.added == 3
    assert chapter.deleted == 0
