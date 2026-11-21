"""The build pipeline: git log -> chapters -> summaries -> audio -> folder."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .audio import narrate
from .core.cite import annotate
from .core.cluster import DEFAULT_MAX_COMMITS, DEFAULT_SIMILARITY, build_chapters
from .core.gitlog import GitError, diff_excerpt, head_sha, is_git_repo, read_commits, repo_name, resolve_since
from .html import write_site
from .i18n import kind_rationale, normalize_lang, source_label, t
from .llm import config_from_env, make_client
from .summarize import summarize_chapters

# The whole build must stay well inside 120 seconds, audio included.
TIME_BUDGET_S = 100.0
AUDIO_BUDGET_S = 70.0


class BuildError(RuntimeError):
    pass


@dataclass
class BuildOptions:
    repo: str
    since: str | None = None
    out: str = "chronicle-out"
    lang: str = "en"
    similarity: float = DEFAULT_SIMILARITY
    max_commits: int = DEFAULT_MAX_COMMITS
    audio: bool = True
    llm: bool = True
    diff_files: int = 3
    diff_lines: int = 30

    def __post_init__(self):
        self.lang = normalize_lang(self.lang)


@dataclass
class BuildReport:
    out_dir: str
    index_path: str
    chapters: int = 0
    commits: int = 0
    audio_ok: int = 0
    audio_failed: int = 0
    audio_silent: int = 0
    engine: str = ""
    model: str | None = None
    sources: dict = field(default_factory=dict)
    dropped_sentences: int = 0
    elapsed_s: float = 0.0
    payload: dict | None = None

    def summary_lines(self) -> list[str]:
        lines = [
            "chapters      %d (%d commits)" % (self.chapters, self.commits),
            "engine        %s" % self.engine,
            "audio         %d narrated, %d silent, %d failed"
            % (self.audio_ok - self.audio_silent, self.audio_silent, self.audio_failed),
            "sources       %s" % ", ".join(
                "%s=%d" % (key, value) for key, value in sorted(self.sources.items())
            ),
            "dropped       %d sentence(s) without valid citations" % self.dropped_sentences,
            "elapsed       %.1fs" % self.elapsed_s,
            "output        %s" % self.index_path,
        ]
        return lines

    def to_dict(self) -> dict:
        return {
            "out_dir": self.out_dir,
            "index_path": self.index_path,
            "chapters": self.chapters,
            "commits": self.commits,
            "audio_ok": self.audio_ok,
            "audio_failed": self.audio_failed,
            "audio_silent": self.audio_silent,
            "engine": self.engine,
            "model": self.model,
            "sources": dict(self.sources),
            "dropped_sentences": self.dropped_sentences,
            "elapsed_s": round(self.elapsed_s, 2),
        }


def narration_text(chapter, sentences: list[str], lang: str) -> str:
    head = t("chapter", lang) + " " + str(chapter.index) + ". " + chapter.title + "."
    return head + " " + " ".join(sentences)


def _chapter_payload(repo: str, chapter, result, lang: str, opts: BuildOptions) -> dict:
    evidence = result.evidence
    annotated = [annotate(sentence, evidence) for sentence in result.sentences]
    files = sorted(
        (
            {
                "path": path,
                "added": stats["added"],
                "deleted": stats["deleted"],
                "commits": stats["commits"],
            }
            for path, stats in chapter.files_by_path.items()
        ),
        key=lambda item: (-(item["added"] + item["deleted"]), item["path"]),
    )
    issues: list[str] = []
    for commit in chapter.commits:
        for issue in commit.issue_refs:
            if str(issue) not in issues:
                issues.append(str(issue))

    diffs: list[dict] = []
    for item in files[: opts.diff_files]:
        path = item["path"]
        source_commit = None
        for commit in reversed(chapter.commits):
            if any(change.path == path for change in commit.files):
                source_commit = commit
                break
        if source_commit is None:
            continue
        try:
            excerpt = diff_excerpt(repo, source_commit.sha, path, max_lines=opts.diff_lines)
        except GitError:
            continue
        if excerpt.lines:
            diffs.append(
                {
                    "path": path,
                    "sha": source_commit.short,
                    "truncated": excerpt.truncated,
                    "lines": excerpt.lines,
                }
            )

    return {
        "index": chapter.index,
        "title": chapter.title,
        "kind": chapter.kind,
        "scope": chapter.scope,
        "lang": lang,
        "sentences": list(result.sentences),
        "sentences_annotated": [
            [
                [text, citation.kind if citation else None, citation.value if citation else None]
                for text, citation in pairs
            ]
            for pairs in annotated
        ],
        "summary": result.text,
        "source": result.source,
        "source_label": source_label(result.source, lang),
        "why": kind_rationale(chapter.kind, lang),
        "commits": [commit.to_dict() for commit in chapter.commits],
        "files": files,
        "issues": issues,
        "added": chapter.added,
        "deleted": chapter.deleted,
        "start": chapter.start,
        "end": chapter.end,
        "diff": diffs,
        "audio": None,
        "audio_engine": None,
        "audio_bytes": 0,
        "audio_duration": None,
        "dropped": [
            {
                "reason": entry.get("reason"),
                "attempts": entry.get("attempts"),
                "unknown_count": len(entry.get("unknown") or []),
            }
            for entry in (result.enforcement.to_dict()["dropped"] if result.enforcement else [])
        ],
        "model": result.model,
    }


def build(opts: BuildOptions, client=None, log=None, allow_tts: bool | None = None) -> BuildReport:
    start = time.time()
    say = log or (lambda message: None)
    lang = opts.lang

    if not os.path.isdir(opts.repo):
        raise BuildError("repository path does not exist: %s" % opts.repo)
    if not is_git_repo(opts.repo):
        raise BuildError("not a git repository: %s" % opts.repo)

    since_sha = None
    if opts.since:
        since_sha = resolve_since(opts.repo, opts.since)
        say("since %s -> %s" % (opts.since, since_sha[:12]))

    commits = read_commits(opts.repo, since=since_sha)
    if not commits:
        raise BuildError("no commits to narrate (check --since)")
    say("read %d commit(s)" % len(commits))

    chapters = build_chapters(commits, similarity=opts.similarity, max_commits=opts.max_commits)
    say("clustered into %d chapter(s)" % len(chapters))

    if client is None and opts.llm:
        client = make_client(config_from_env())
    if client is not None and not getattr(client, "available", False):
        client = None

    deadline = start + TIME_BUDGET_S
    results = summarize_chapters(chapters, lang=lang, client=client, repo_name=repo_name(opts.repo), deadline=deadline)
    say("summaries: %s" % ", ".join("%s=%d" % (k, v) for k, v in _source_counts(results).items()))

    os.makedirs(opts.out, exist_ok=True)
    audio_dir = os.path.join(opts.out, "audio")
    audio_start = time.time()
    payload_chapters: list[dict] = []
    sources: dict = {}
    dropped = 0
    audio_ok = 0
    audio_failed = 0
    audio_silent = 0

    for chapter, result in zip(chapters, results):
        item = _chapter_payload(opts.repo, chapter, result, lang, opts)
        sources[result.source] = sources.get(result.source, 0) + 1
        dropped += len(item["dropped"])

        want_audio = (allow_tts is None and opts.audio) if allow_tts is None else allow_tts
        if want_audio:
            budget_left = AUDIO_BUDGET_S - (time.time() - audio_start)
            text = narration_text(chapter, result.sentences, lang)
            if budget_left < 8:
                from .audio import write_silence

                path = os.path.join(audio_dir, "chapter-%02d.wav" % chapter.index)
                audio = write_silence(path, seconds=max(2.0, min(20.0, len(text) / 14.0)))
                audio.error = "audio budget exhausted"
            else:
                path = os.path.join(audio_dir, "chapter-%02d.mp3" % chapter.index)
                audio = narrate(
                    text,
                    path,
                    lang=lang,
                    allow_tts=True,
                    timeout=int(min(40, max(15, budget_left))),
                )
            if audio.ok:
                audio_ok += 1
                if audio.engine == "silence":
                    audio_silent += 1
                item["audio"] = os.path.relpath(audio.path, opts.out).replace(os.sep, "/")
                item["audio_engine"] = audio.engine
                item["audio_bytes"] = audio.bytes
                item["audio_duration"] = audio.duration_s
                say("audio %02d %s" % (chapter.index, audio.engine))
            else:
                audio_failed += 1
                say("audio %02d failed: %s" % (chapter.index, audio.error))
        payload_chapters.append(item)

    head = head_sha(opts.repo)
    meta = {
        "title": "Chronicle",
        "tagline": t("tagline", lang),
        "repo": repo_name(opts.repo) or opts.repo,
        "lang": lang,
        "generated": datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M %Z"),
        "head": head[:7],
        "since": since_sha[:7] if since_sha else None,
        "since_label": opts.since,
        "first_date": (chapters[0].start or "")[:10],
        "last_date": (chapters[-1].end or "")[:10],
        "commits": len(commits),
        "chapters": len(chapters),
        "engine": "openai-compat" if client is not None else "deterministic",
        "model": getattr(getattr(client, "config", None), "model", None),
        "engine_label": (
            "LLM: " + str(getattr(getattr(client, "config", None), "model", "openai-compat"))
            if client is not None
            else t("engine_deterministic", lang)
        ),
        "footer": t("footer", lang),
        "sources": sources,
        "dropped": dropped,
    }
    payload = {"meta": meta, "chapters": payload_chapters}

    index_path = write_site(payload, opts.out, lang)
    with open(os.path.join(opts.out, "chronicle.json"), "w", encoding="utf-8") as handle:
        import json

        json.dump(payload, handle, ensure_ascii=False, indent=2)

    elapsed = time.time() - start
    return BuildReport(
        out_dir=opts.out,
        index_path=index_path,
        chapters=len(chapters),
        commits=len(commits),
        audio_ok=audio_ok,
        audio_failed=audio_failed,
        audio_silent=audio_silent,
        engine=meta["engine_label"],
        model=meta["model"],
        sources=sources,
        dropped_sentences=dropped,
        elapsed_s=elapsed,
        payload=payload,
    )


def _source_counts(results) -> dict:
    counts: dict = {}
    for result in results:
        counts[result.source] = counts.get(result.source, 0) + 1
    return counts
