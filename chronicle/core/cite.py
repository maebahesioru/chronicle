"""The citation contract.

Chronicle refuses to publish a sentence that cannot be traced back to the
repository. A sentence is valid when it contains at least one citation that
points at real evidence from its chapter:

  * a commit SHA (7 to 40 hex characters, at least one letter and one digit),
  * a file path that the chapter actually touched,
  * an issue number (#123) that appears in the chapter's commit messages.

Citations that merely look valid but are absent from the evidence are
treated as errors, not as decoration. That is what keeps the narrated
summary honest: a hallucinated SHA loses the whole sentence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SHA_RE = re.compile(r"(?<![0-9a-zA-Z])[0-9a-fA-F]{7,40}(?![0-9a-zA-Z])")
PATH_RE = re.compile(
    r"(?<![\w/.\-])((?:[\w.\-]+/)*[\w.\-]+\.[A-Za-z][A-Za-z0-9]{0,7})(?![\w/\-])"
)
ISSUE_RE = re.compile(r"(?<![\w&])#(\d{1,6})\b")

SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？])|(?<=[.!?])\s+")

CITATION_KIND_SHA = "sha"
CITATION_KIND_PATH = "path"
CITATION_KIND_ISSUE = "issue"


@dataclass(frozen=True)
class Citation:
    kind: str
    value: str

    @property
    def label(self) -> str:
        if self.kind == CITATION_KIND_ISSUE:
            return "#" + self.value
        return self.value


@dataclass
class Evidence:
    """Everything a chapter is allowed to cite."""

    shas: list[str] = field(default_factory=list)
    paths: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.shas = sorted({s for s in self.shas if s})
        self.paths = sorted({p for p in self.paths if p})
        self.issues = sorted({str(i) for i in self.issues if str(i)})
        self._sha_set = set(self.shas)
        self._path_set = set(self.paths)
        self._issue_set = set(self.issues)

    def knows_sha(self, token: str) -> bool:
        token = token.lower()
        if token in self._sha_set:
            return True
        return any(full.lower().startswith(token) for full in self.shas)

    def knows_path(self, token: str) -> bool:
        return token in self._path_set

    def knows_issue(self, token: str) -> bool:
        return token.lstrip("#") in self._issue_set

    def prompt_block(self) -> str:
        lines = ["CITABLE COMMIT SHAS:"]
        lines.extend("- " + sha for sha in self.shas)
        lines.append("CITABLE FILE PATHS:")
        lines.extend("- " + path for path in self.paths)
        lines.append("CITABLE ISSUE NUMBERS:")
        lines.extend("- #" + issue for issue in self.issues)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {"shas": list(self.shas), "paths": list(self.paths), "issues": list(self.issues)}


def _looks_like_sha(token: str) -> bool:
    if len(token) < 7 or len(token) > 40:
        return False
    has_letter = any(c in "abcdefABCDEF" for c in token)
    has_digit = any(c.isdigit() for c in token)
    return has_letter and has_digit


def find_citations(sentence: str) -> list[Citation]:
    """Extract every citation-shaped token from a sentence (order preserved)."""
    found: list[tuple[int, Citation]] = []
    masked = sentence

    for match in SHA_RE.finditer(sentence):
        token = match.group(0)
        if _looks_like_sha(token):
            found.append((match.start(), Citation(CITATION_KIND_SHA, token)))
            masked = masked[: match.start()] + " " * (match.end() - match.start()) + masked[match.end():]

    for match in PATH_RE.finditer(masked):
        token = match.group(1)
        if "/" in token or token.count(".") >= 1:
            found.append((match.start(1), Citation(CITATION_KIND_PATH, token)))

    for match in ISSUE_RE.finditer(masked):
        found.append((match.start(), Citation(CITATION_KIND_ISSUE, match.group(1))))

    found.sort(key=lambda item: item[0])
    return [citation for _, citation in found]


def citation_ok(citation: Citation, evidence: Evidence) -> bool:
    if citation.kind == CITATION_KIND_SHA:
        return evidence.knows_sha(citation.value)
    if citation.kind == CITATION_KIND_PATH:
        return evidence.knows_path(citation.value)
    if citation.kind == CITATION_KIND_ISSUE:
        return evidence.knows_issue(citation.value)
    return False


@dataclass
class Verdict:
    ok: bool
    citations: list[Citation] = field(default_factory=list)
    unknown: list[Citation] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "citations": [c.label for c in self.citations],
            "unknown": [c.label for c in self.unknown],
        }


def inspect_sentence(sentence: str, evidence: Evidence) -> Verdict:
    """Decide whether one sentence honours the citation contract."""
    text = (sentence or "").strip()
    if not text:
        return Verdict(ok=False, reason="empty")
    citations = find_citations(text)
    good = [c for c in citations if citation_ok(c, evidence)]
    bad = [c for c in citations if not citation_ok(c, evidence)]
    if bad:
        return Verdict(
            ok=False,
            citations=good,
            unknown=bad,
            reason="unknown-citation",
        )
    if not good:
        return Verdict(ok=False, reason="no-citation")
    return Verdict(ok=True, citations=good, reason="ok")


def validate_sentence(sentence: str, evidence: Evidence) -> bool:
    return inspect_sentence(sentence, evidence).ok


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, keeping Japanese full stops intact."""
    text = (text or "").strip()
    if not text:
        return []
    parts: list[str] = []
    buffer = ""
    for chunk in SENTENCE_SPLIT_RE.split(text):
        if chunk is None:
            continue
        piece = chunk.strip()
        if not piece:
            continue
        buffer = piece if not buffer else buffer + piece
        if buffer and buffer[-1] in "。！？.!?":
            parts.append(buffer.strip())
            buffer = ""
    if buffer.strip():
        parts.append(buffer.strip())
    return [p for p in parts if p]


@dataclass
class Enforcement:
    """Outcome of running the contract over a candidate summary."""

    sentences: list[str] = field(default_factory=list)
    kept: int = 0
    dropped: list[dict] = field(default_factory=list)
    regenerated: int = 0
    used_fallback: bool = False

    @property
    def text(self) -> str:
        return " ".join(self.sentences)

    def to_dict(self) -> dict:
        return {
            "sentences": list(self.sentences),
            "kept": self.kept,
            "dropped": [dict(item) for item in self.dropped],
            "regenerated": self.regenerated,
            "used_fallback": self.used_fallback,
        }


def enforce(
    text: str,
    evidence: Evidence,
    regenerate=None,
    max_attempts: int = 2,
    fallback=None,
) -> Enforcement:
    """Keep only sentences that satisfy the contract.

    regenerate(index, previous_sentence) may return a replacement string; it
    is called at most max_attempts times per sentence. fallback() is used when
    nothing survives, so the player always has something true to say.
    """
    result = Enforcement()
    for index, sentence in enumerate(split_sentences(text)):
        verdict = inspect_sentence(sentence, evidence)
        attempts = 0
        while not verdict.ok and regenerate is not None and attempts < max_attempts:
            attempts += 1
            try:
                replacement = regenerate(index, sentence)
            except Exception:  # a broken backend must not kill the build
                replacement = None
            result.regenerated += 1
            candidate = (replacement or "").strip()
            if not candidate:
                break
            verdict = inspect_sentence(candidate, evidence)
            sentence = candidate
        if verdict.ok:
            result.sentences.append(sentence.strip())
            result.kept += 1
        else:
            result.dropped.append(
                {
                    "sentence": sentence,
                    "reason": verdict.reason,
                    "unknown": [c.label for c in verdict.unknown],
                    "attempts": attempts,
                }
            )

    if not result.sentences and fallback is not None:
        replacement = fallback()
        for sentence in split_sentences(replacement or ""):
            if validate_sentence(sentence, evidence):
                result.sentences.append(sentence.strip())
        result.used_fallback = True
        result.kept = len(result.sentences)
    return result


def annotate(sentence: str, evidence: Evidence) -> list[tuple[str, Citation | None]]:
    """Split a sentence into plain text and citation runs for HTML rendering."""
    spans: list[tuple[int, int, Citation]] = []
    masked = sentence
    for match in SHA_RE.finditer(sentence):
        token = match.group(0)
        if _looks_like_sha(token):
            citation = Citation(CITATION_KIND_SHA, token)
            if citation_ok(citation, evidence):
                spans.append((match.start(), match.end(), citation))
            masked = masked[: match.start()] + " " * (match.end() - match.start()) + masked[match.end():]
    for match in PATH_RE.finditer(masked):
        citation = Citation(CITATION_KIND_PATH, match.group(1))
        if citation_ok(citation, evidence):
            spans.append((match.start(1), match.end(1), citation))
    for match in ISSUE_RE.finditer(masked):
        citation = Citation(CITATION_KIND_ISSUE, match.group(1))
        if citation_ok(citation, evidence):
            spans.append((match.start(), match.end(), citation))

    spans.sort(key=lambda item: item[0])
    out: list[tuple[str, Citation | None]] = []
    cursor = 0
    for start, end, citation in spans:
        if start < cursor:
            continue
        if start > cursor:
            out.append((sentence[cursor:start], None))
        out.append((sentence[start:end], citation))
        cursor = end
    if cursor < len(sentence):
        out.append((sentence[cursor:], None))
    return out
