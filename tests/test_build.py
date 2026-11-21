"""End-to-end builds: self-contained HTML, --since, and the contract in anger."""

from __future__ import annotations

from chronicle.build import BuildOptions, build
from chronicle.core.cite import Evidence, validate_sentence
from chronicle.summarize import evidence_for


def chapter_evidence(item: dict) -> Evidence:
    return Evidence(
        shas=[commit["sha"] for commit in item["commits"]],
        paths=[entry["path"] for entry in item["files"]],
        issues=[str(issue) for issue in item["issues"]],
    )


def test_build_writes_a_self_contained_player(sample_repo, tmp_path):
    out = tmp_path / "site"
    report = build(
        BuildOptions(repo=str(sample_repo), out=str(out), lang="en", audio=False, llm=False)
    )
    html = (out / "index.html").read_text(encoding="utf-8")

    assert report.chapters >= 3
    assert (out / "chronicle.json").exists()
    assert "http://" not in html
    assert "https://" not in html
    assert "<style>" in html
    assert "<script" in html
    assert "cite-sha" in html
    assert "cite-path" in html
    assert 'rel="stylesheet"' not in html
    assert "class=\"diff\"" in html


def test_every_narrated_sentence_keeps_the_contract(sample_repo, tmp_path):
    report = build(
        BuildOptions(
            repo=str(sample_repo),
            out=str(tmp_path / "site"),
            lang="en",
            audio=False,
            llm=False,
        )
    )
    for item in report.payload["chapters"]:
        evidence = evidence_for
        evidence = Evidence(
            shas=[commit["sha"] for commit in item["commits"]],
            paths=[entry["path"] for entry in item["files"]],
            issues=[str(issue) for issue in item["issues"]],
        )
        assert item["sentences"]
        for sentence in item["sentences"]:
            assert validate_sentence(sentence, evidence), (item["title"], sentence)


def test_since_release_mode_limits_the_story(sample_repo, tmp_path):
    out = tmp_path / "release"
    report = build(
        BuildOptions(
            repo=str(sample_repo),
            since="v0.1.0",
            out=str(out),
            lang="ja",
            audio=False,
            llm=False,
        )
    )
    assert report.commits == 2
    meta = report.payload["meta"]
    assert meta["since"]
    assert meta["lang"] == "ja"
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "第1章" in html or "chapter" in html


class HallucinatingClient:
    available = True
    model = "fake-model"

    def complete(self, system: str, user: str, max_tokens: int = 500) -> str:
        return (
            "This claim invents commit deadbeef00 and must be cut. "
            "The parser work landed in src/core/parser.py."
        )


def test_hallucinated_sentences_are_dropped_and_counted(sample_repo, tmp_path):
    out = tmp_path / "llm-site"
    report = build(
        BuildOptions(repo=str(sample_repo), out=str(out), lang="en", audio=False, llm=True),
        client=HallucinatingClient(),
    )
    assert report.dropped_sentences >= 1
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "deadbeef00" not in html
    for item in report.payload["chapters"]:
        evidence = Evidence(
            shas=[commit["sha"] for commit in item["commits"]],
            paths=[entry["path"] for entry in item["files"]],
            issues=[str(issue) for issue in item["issues"]],
        )
        for sentence in item["sentences"]:
            assert validate_sentence(sentence, evidence)
