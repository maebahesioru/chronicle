"""The citation contract: no citation, no sentence."""

from __future__ import annotations

import pytest

from chronicle.core.cite import (
    Enforcement,
    Evidence,
    enforce,
    find_citations,
    inspect_sentence,
    split_sentences,
    validate_sentence,
)
from chronicle.core.model import Chapter, Commit


EVIDENCE = Evidence(
    shas=["a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"],
    paths=["src/core/parser.py", "docs/guide.md"],
    issues=["42"],
)


def test_sentence_without_citation_is_rejected():
    verdict = inspect_sentence("The parser got better over time.", EVIDENCE)
    assert verdict.ok is False
    assert verdict.reason == "no-citation"


def test_sentence_with_known_path_passes():
    verdict = inspect_sentence("The work concentrated in src/core/parser.py.", EVIDENCE)
    assert verdict.ok is True
    assert verdict.reason == "ok"


def test_sentence_with_known_sha_passes():
    verdict = inspect_sentence("Commit a1b2c3d opened the story.", EVIDENCE)
    assert verdict.ok is True


def test_invented_sha_is_rejected_even_next_to_a_real_citation():
    verdict = inspect_sentence("Commit badc0de1 touched src/core/parser.py.", EVIDENCE)
    assert verdict.ok is False
    assert verdict.reason == "unknown-citation"


def test_issue_number_must_exist_in_the_chapter():
    assert validate_sentence("This closes #42.", EVIDENCE) is True
    assert validate_sentence("This closes #7.", EVIDENCE) is False


def test_dates_and_versions_are_not_mistaken_for_shas():
    sentence = "Shipped 2026-11-21 with python 3.14.9 and docs/guide.md."
    verdict = inspect_sentence(sentence, EVIDENCE)
    assert verdict.ok is True
    kinds = {citation.kind for citation in find_citations(sentence)}
    assert "sha" not in kinds
    assert "path" in kinds


def test_enforce_drops_uncited_sentence_and_keeps_cited_one():
    text = "This paragraph is pure vibes. It touched src/core/parser.py in practice."
    result = enforce(text, EVIDENCE)
    assert result.kept == 1
    assert len(result.sentences) == 1
    assert "src/core/parser.py" in result.sentences[0]
    assert len(result.dropped) == 1
    assert "pure vibes" in result.dropped[0]["sentence"]
    assert result.dropped[0]["reason"] == "no-citation"


def test_enforce_regenerates_a_rejected_sentence_once():
    calls = []

    def regenerate(index, sentence):
        calls.append((index, sentence))
        return "Repaired sentence about docs/guide.md."

    text = "A sentence with no citation at all."
    result = enforce(text, EVIDENCE, regenerate=regenerate)
    assert calls
    assert result.regenerated == 1
    assert result.sentences == ["Repaired sentence about docs/guide.md."]


def test_enforce_falls_back_when_regeneration_stays_uncited():
    text = "Nothing citeable here."
    result = enforce(text, EVIDENCE, regenerate=lambda index, sentence: "Still nothing citeable.")
    assert result.sentences == []
    assert result.kept == 0
    assert result.used_fallback is False


def test_enforce_uses_a_validated_fallback():
    text = "Nothing citeable here."
    result = enforce(
        text,
        EVIDENCE,
        regenerate=lambda index, sentence: "Still nothing citeable.",
        fallback=lambda: "Fallback mentions src/core/parser.py.",
    )
    assert result.sentences == ["Fallback mentions src/core/parser.py."]
    assert result.used_fallback is True


def test_split_sentences_keeps_japanese_periods():
    parts = split_sentences("最初の文です。二つ目の文です。")
    assert parts == ["最初の文です。", "二つ目の文です。"]


def test_deterministic_summary_always_satisfies_the_contract():
    from chronicle.summarize import deterministic_summary, evidence_for

    commits = [
        Commit(
            sha="a1b2c3d4e5f60718293a4b5c6d7e8f9012345678",
            short="a1b2c3d",
            author="Test",
            date="2026-11-21T10:00:00+09:00",
            subject="feat(parser): add parser",
            files=[],
        )
    ]
    chapter = Chapter(index=1, commits=commits)
    evidence = evidence_for(chapter)
    for lang in ("en", "ja"):
        text = deterministic_summary(chapter, lang=lang, evidence=evidence)
        sentences = split_sentences(text)
        assert len(sentences) >= 2, (lang, text)
        assert all(validate_sentence(sentence, evidence) for sentence in sentences), (lang, text)
