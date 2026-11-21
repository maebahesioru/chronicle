"""English and Japanese strings used by the narrator and the HTML player."""

from __future__ import annotations

LANGS = ("ja", "en")

KIND_LABEL = {
    "en": {
        "feat": "feature",
        "fix": "bug fix",
        "docs": "documentation",
        "test": "tests",
        "refactor": "refactor",
        "perf": "performance",
        "chore": "maintenance",
        "build": "build",
        "ci": "CI",
        "style": "formatting",
        "revert": "revert",
        "other": "work",
    },
    "ja": {
        "feat": "新機能",
        "fix": "不具合修正",
        "docs": "ドキュメント",
        "test": "テスト",
        "refactor": "リファクタ",
        "perf": "性能改善",
        "chore": "保守作業",
        "build": "ビルド",
        "ci": "CI",
        "style": "整形",
        "revert": "差し戻し",
        "other": "作業",
    },
}

KIND_RATIONALE = {
    "en": {
        "feat": "someone needed a capability that did not exist yet",
        "fix": "a defect was closing the door on real use",
        "docs": "the written surface had to catch up with the code",
        "test": "behaviour needed to be pinned before it drifted",
        "refactor": "the shape of the code was the obstacle",
        "perf": "the work was too slow or too heavy",
        "chore": "plumbing had to be kept alive",
        "build": "the build itself had to change",
        "ci": "automation took over a manual chore",
        "style": "only the surface changed",
        "revert": "an earlier decision was rolled back",
        "other": "the intent is only visible in the diff",
    },
    "ja": {
        "feat": "まだ存在しない機能が求められていた",
        "fix": "不具合が実際の利用を妨げていた",
        "docs": "書かれた説明がコードに追いつく必要があった",
        "test": "挙動がずれる前に固定する必要があった",
        "refactor": "コードの形そのものが障害になっていた",
        "perf": "処理が遅いか重すぎた",
        "chore": "土台の配管を生かしておく必要があった",
        "build": "ビルドの仕組み自体を変える必要があった",
        "ci": "手作業を自動化する必要があった",
        "style": "見た目だけが変わった",
        "revert": "以前の判断が取り消された",
        "other": "意図は diff からしか読み取れない",
    },
}

UI = {
    "en": {
        "engine_deterministic": "deterministic mode (no API key)",
        "engine_llm": "LLM mode",
        "title": "Chronicle",
        "tagline": "hear why your code exists",
        "chapters": "Chapters",
        "chapter": "Chapter",
        "play": "Play",
        "pause": "Pause",
        "stop": "Stop",
        "citations": "Citations",
        "evidence": "Evidence",
        "commits": "commits",
        "files": "files",
        "diff": "Diff highlight",
        "why": "Why",
        "no_audio": "No audio for this chapter (text only)",
        "generated_by": "Summary source",
        "repo": "Repository",
        "range": "Range",
        "since": "Since",
        "head": "HEAD",
        "built": "Built",
        "offline": "This folder is self-contained: no network requests, no CDN.",
        "next": "next chapter",
        "now": "now playing",
        "total": "total",
        "duration": "duration",
        "lang": "Language",
        "empty": "No chapters were produced.",
    },
    "ja": {
        "engine_deterministic": "決定論モード（APIキーなし）",
        "engine_llm": "LLMモード",
        "title": "Chronicle",
        "tagline": "コードが存在する理由を、聴く",
        "chapters": "章一覧",
        "chapter": "第",
        "play": "再生",
        "pause": "一時停止",
        "stop": "停止",
        "citations": "引用",
        "evidence": "根拠",
        "commits": "コミット",
        "files": "ファイル",
        "diff": "差分ハイライト",
        "why": "なぜ",
        "no_audio": "この章に音声はありません（テキストのみ）",
        "generated_by": "要約の生成元",
        "repo": "リポジトリ",
        "range": "範囲",
        "since": "起点",
        "head": "HEAD",
        "built": "生成",
        "offline": "このフォルダは自己完結しています。外部CDN・通信はありません。",
        "next": "次の章",
        "now": "再生中",
        "total": "全",
        "duration": "長さ",
        "lang": "言語",
        "empty": "章がありません。",
    },
}

SUMMARY_SOURCE_LABEL = {
    "en": {
        "llm": "language model, citation-checked",
        "deterministic": "deterministic fallback (diff stat)",
        "deterministic-fallback": "language model rejected by validator, deterministic fallback used",
        "mixed": "language model + deterministic fills",
    },
    "ja": {
        "llm": "言語モデル（引用検証済み）",
        "deterministic": "決定論フォールバック（diff stat）",
        "deterministic-fallback": "言語モデルが検証で落ち、決定論に切替",
        "mixed": "言語モデル＋決定論の併用",
    },
}


def normalize_lang(value: str | None) -> str:
    if value and value.lower().startswith("ja"):
        return "ja"
    return "en"


def kind_label(kind: str, lang: str = "en") -> str:
    return KIND_LABEL.get(lang, KIND_LABEL["en"]).get(kind, kind)


def kind_rationale(kind: str, lang: str = "en") -> str:
    return KIND_RATIONALE.get(lang, KIND_RATIONALE["en"]).get(kind, "")


def t(key: str, lang: str = "en") -> str:
    table = UI.get(lang, UI["en"])
    return table.get(key) or UI["en"].get(key) or key


def source_label(source: str, lang: str = "en") -> str:
    table = SUMMARY_SOURCE_LABEL.get(lang, SUMMARY_SOURCE_LABEL["en"])
    return table.get(source, source)
