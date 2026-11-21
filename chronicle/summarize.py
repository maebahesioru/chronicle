"""Chapter narration with the citation contract wrapped around every backend.

Two summary engines exist:

* deterministic: built from the diff stat and commit metadata. It needs no
  network, no API key and no model, and it is always available.
* openai-compat: any chat-completions endpoint. Its prose is fed through the
  same validator, and every rejected sentence is either repaired once or
  replaced by the deterministic text.

The deterministic engine writes sentences that cite a SHA and a path on
purpose: the fallback must obey the contract too, otherwise the contract is
just decoration.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .core.cite import Evidence, Enforcement, enforce, find_citations, split_sentences, validate_sentence
from .core.model import Chapter
from .i18n import kind_label, kind_rationale, normalize_lang
from .llm import LLMError

REPAIR_SYSTEM = {
    "en": (
        "You repair one sentence so it satisfies a citation contract. "
        "Return only the rewritten sentence, in English, one sentence, no preamble. "
        "It must contain at least one token copied exactly from the CITABLE list."
    ),
    "ja": (
        "あなたは引用契約を満たすように文を1つだけ書き直す。"
        "英語や前置きは書かず、日本語の文を1つだけ返す。"
        "CITABLE の一覧からそのままコピーした語を最低1つ含めること。"
    ),
}


def evidence_for(chapter: Chapter) -> Evidence:
    shas = [commit.sha for commit in chapter.commits]
    paths = chapter.paths
    issues: list[str] = []
    for commit in chapter.commits:
        for issue in commit.issue_refs:
            issues.append(str(issue))
    return Evidence(shas=shas, paths=paths, issues=issues)


def _date(value: str) -> str:
    return (value or "")[:10]


def _scrub(text: str, evidence: Evidence) -> str:
    """Remove citation-shaped tokens that are not backed by this chapter."""
    cleaned = text or ""
    for citation in find_citations(cleaned):
        valid = (
            (citation.kind == "sha" and evidence.knows_sha(citation.value))
            or (citation.kind == "path" and evidence.knows_path(citation.value))
            or (citation.kind == "issue" and evidence.knows_issue(citation.value))
        )
        if not valid:
            cleaned = cleaned.replace(citation.value, "")
    cleaned = cleaned.replace("（）", "").replace("()", "").replace("  ", " ")
    cleaned = cleaned.replace(" ,", ",").replace(" 。", "。").replace(" .", ".")
    return cleaned.strip(" ,;:-")


def _top_files(chapter: Chapter, limit: int = 1) -> list[tuple[str, int, int]]:
    ranked = sorted(
        (
            (path, stats["added"], stats["deleted"])
            for path, stats in chapter.files_by_path.items()
        ),
        key=lambda item: (-(item[1] + item[2]), item[0]),
    )
    return ranked[:limit]


def _count(n: int, singular: str, plural: str) -> str:
    return ("1 " + singular) if n == 1 else ("%d %s" % (n, plural))


def _issues_note(chapter: Chapter, lang: str) -> str:
    issues: list[str] = []
    for commit in chapter.commits:
        for issue in commit.issue_refs:
            token = "#" + str(issue)
            if token not in issues:
                issues.append(token)
    if not issues:
        return ""
    joined = " and ".join(issues[:3]) if lang == "en" else "・".join(issues[:3])
    return (" (closes " + joined + ")") if lang == "en" else ("（" + joined + " に対応）")


def deterministic_summary(chapter: Chapter, lang: str = "en", evidence: Evidence | None = None) -> str:
    """Build the always-available two-sentence summary from the diff stat."""
    lang = normalize_lang(lang)
    evidence = evidence or evidence_for(chapter)
    commits = chapter.commits
    first, last = commits[0], commits[-1]
    n = len(commits)
    files = chapter.files_by_path
    k = len(files)
    added, deleted = chapter.added, chapter.deleted
    kind = chapter.kind
    label = kind_label(kind, lang)
    rationale = kind_rationale(kind, lang)
    top = _top_files(chapter, 1)
    top_path, top_add, top_del = (top[0] if top else ("", 0, 0))
    cite_path = top_path or (chapter.paths[0] if chapter.paths else "")
    first_subject = _scrub(first.subject, evidence)
    last_subject = _scrub(last.subject, evidence)
    issues_note = _issues_note(chapter, lang)

    if lang == "ja":
        s1 = (
            "第%d章は%sから%sまでの%dコミットで%dファイル（+%d/-%d）を変更し、"
            "中心にある意図は%s、つまり%sです（起点は %s、最も大きく動いたのは %s）。"
            % (chapter.index, _date(chapter.start), _date(chapter.end), n, k, added, deleted, label, rationale, first.short, cite_path)
        )
        if n == 1:
            s2 = (
                "唯一のコミット %s「%s」が変更を %s（+%d/-%d）に集中させています%s。"
                % (first.short, first_subject, top_path, top_add, top_del, issues_note)
            )
        else:
            s2 = (
                "流れは %s「%s」から %s「%s」へ進み、最も大きく動いたのは %s（+%d/-%d）です%s。"
                % (first.short, first_subject, last.short, last_subject, top_path, top_add, top_del, issues_note)
            )
    else:
        s1 = (
            "Chapter %d gathers %s between %s and %s that touched %s (+%d/-%d), "
            "and its dominant intent is %s: %s (starting at %s, heaviest edit in %s)."
            % (
                chapter.index,
                _count(n, "commit", "commits"),
                _date(chapter.start),
                _date(chapter.end),
                _count(k, "file", "files"),
                added,
                deleted,
                label,
                rationale,
                first.short,
                cite_path,
            )
        )
        if n == 1:
            s2 = (
                "The single commit %s (%s) concentrated its change in %s (+%d/-%d)%s."
                % (first.short, first_subject, top_path, top_add, top_del, issues_note)
            )
        else:
            s2 = (
                "The trail runs from %s (%s) to %s (%s), and the heaviest edit landed in %s (+%d/-%d)%s."
                % (first.short, first_subject, last.short, last_subject, top_path, top_add, top_del, issues_note)
            )

    return s1 + " " + s2 if lang == "en" else s1 + s2


def summary_prompt(chapter: Chapter, lang: str = "en", repo_name: str = "", evidence: Evidence | None = None) -> tuple[str, str]:
    lang = normalize_lang(lang)
    evidence = evidence or evidence_for(chapter)
    if lang == "ja":
        system = (
            "あなたは Chronicle。コミット群が「なぜ存在するのか」を語るナレーターである。\n"
            "規則:\n"
            "1. 日本語で必ず2文だけ書く。\n"
            "2. 各文には CITABLE の一覧からそのままコピーした引用語（コミットSHA・ファイルパス・#番号）を最低1つ含める。\n"
            "3. SHA・パス・issue番号・作者・日付を捏造してはならない。一覧にない語は引用として書かない。\n"
            "4. ファイル単位の作業日誌ではなく、意図と原因を説明する。\n"
            "5. 前置き・見出し・箇条書き・コードブロックは禁止。本文2文だけを返す。"
        )
        commit_header = "コミット:"
        file_header = "変更ファイル:"
    else:
        system = (
            "You are Chronicle, a narrator that explains WHY a group of commits exists.\n"
            "Rules:\n"
            "1. Answer with exactly two sentences, in English.\n"
            "2. Every sentence must contain at least one citation token copied verbatim from the CITABLE list "
            "(a commit SHA, a file path, or an issue number such as #12).\n"
            "3. Never invent SHAs, paths, issue numbers, authors or dates. Do not cite anything absent from the lists.\n"
            "4. Explain intent and cause, not a file-by-file diary.\n"
            "5. No preamble, headings, bullet points or code fences. Return the two sentences only."
        )
        commit_header = "COMMITS:"
        file_header = "FILES:"

    lines: list[str] = []
    if repo_name:
        lines.append(("リポジトリ: " if lang == "ja" else "REPOSITORY: ") + repo_name)
    lines.append(("章: " if lang == "ja" else "CHAPTER: ") + chapter.title)
    lines.append(commit_header)
    for commit in chapter.commits:
        lines.append(
            "- %s %s (%s, +%d/-%d)"
            % (commit.short, commit.subject, commit.author, commit.added, commit.deleted)
        )
    lines.append(file_header)
    for path, added_n, deleted_n in _top_files(chapter, 8):
        lines.append("- %s (+%d/-%d)" % (path, added_n, deleted_n))
    lines.append("")
    lines.append(evidence.prompt_block())
    return system, "\n".join(lines)


@dataclass
class SummaryResult:
    chapter: Chapter
    sentences: list[str] = field(default_factory=list)
    source: str = "deterministic"
    evidence: Evidence | None = None
    enforcement: Enforcement | None = None
    model: str | None = None
    error: str | None = None
    elapsed_ms: int = 0

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    def to_dict(self) -> dict:
        payload = {
            "index": self.chapter.index,
            "title": self.chapter.title,
            "sentences": list(self.sentences),
            "source": self.source,
            "model": self.model,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
            "citations": [c.label for c in (self.evidence.shas if self.evidence else [])][:20],
            "dropped": self.enforcement.to_dict()["dropped"] if self.enforcement else [],
        }
        return payload


def _expired(deadline: float | None) -> bool:
    return deadline is not None and time.time() >= deadline


def summarize_chapter(
    chapter: Chapter,
    lang: str = "en",
    client=None,
    repo_name: str = "",
    deadline: float | None = None,
    max_repairs: int = 1,
) -> SummaryResult:
    start = time.time()
    lang = normalize_lang(lang)
    evidence = evidence_for(chapter)
    fallback_text = deterministic_summary(chapter, lang, evidence)
    result = SummaryResult(
        chapter=chapter,
        source="deterministic",
        evidence=evidence,
        enforcement=enforce(fallback_text, evidence),
    )
    result.sentences = list(result.enforcement.sentences)

    if client is None or not getattr(client, "available", False) or _expired(deadline):
        result.elapsed_ms = int((time.time() - start) * 1000)
        return result

    system, user = summary_prompt(chapter, lang, repo_name, evidence)

    def repair(index: int, sentence: str) -> str | None:
        if _expired(deadline):
            return None
        repair_user = (
            "SENTENCE TO REPAIR:\n" + sentence + "\n\n" + evidence.prompt_block()
        )
        try:
            return client.complete(REPAIR_SYSTEM[lang], repair_user, max_tokens=200)
        except LLMError:
            return None

    try:
        raw = client.complete(system, user, max_tokens=400)
    except LLMError as exc:
        result.source = "deterministic"
        result.error = str(exc)
        result.elapsed_ms = int((time.time() - start) * 1000)
        return result

    attempt = enforce(
        raw,
        evidence,
        regenerate=repair,
        max_attempts=max_repairs,
        fallback=None,
    )
    result.enforcement = attempt
    result.model = getattr(client, "config", None) and getattr(client.config, "model", None)

    if attempt.sentences:
        result.sentences = list(attempt.sentences)
        result.source = "llm"
        if len(result.sentences) < 2:
            for candidate in split_sentences(fallback_text):
                if len(result.sentences) >= 2:
                    break
                if validate_sentence(candidate, evidence) and candidate not in result.sentences:
                    result.sentences.append(candidate)
                    result.source = "mixed"
    else:
        result.source = "deterministic-fallback"
        filler = Enforcement()
        for candidate in split_sentences(fallback_text):
            if validate_sentence(candidate, evidence):
                filler.sentences.append(candidate)
        filler.kept = len(filler.sentences)
        filler.used_fallback = True
        filler.dropped = attempt.dropped
        filler.regenerated = attempt.regenerated
        result.sentences = list(filler.sentences)
        result.enforcement = filler

    if not result.sentences:
        # Last resort that still cites a real commit.
        result.sentences = ["Chapter %d covers commit %s." % (chapter.index, chapter.commits[0].short)]
        result.source = "deterministic"

    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def summarize_chapters(
    chapters: list[Chapter],
    lang: str = "en",
    client=None,
    repo_name: str = "",
    deadline: float | None = None,
) -> list[SummaryResult]:
    results: list[SummaryResult] = []
    for chapter in chapters:
        results.append(
            summarize_chapter(
                chapter,
                lang=lang,
                client=client,
                repo_name=repo_name,
                deadline=deadline,
            )
        )
    return results
