# Chronicle - hear why your code exists

**Your git history already knows why the code exists. Chronicle turns it into a narrated, cited book.**

Chronicle reads a local git repository, clusters commits into chapters, writes a two-sentence "why" summary for each chapter, and reads it aloud. The differentiator is a hard **citation contract**: every generated sentence must cite a real commit SHA, a file path from that chapter, or an issue reference found in the commit message. A sentence that cannot be verified is thrown away and regenerated - never shipped.

No API key? Chronicle falls back to a deterministic diff-stat summarizer, so the demo runs completely offline with the same citation guarantees.

## What it does

- Clusters `git log` into chapters: conventional-commit type/scope first, file-set Jaccard similarity for everything else.
- Writes exactly two sentences per chapter with an optional OpenAI-compatible LLM.
- Enforces the citation contract on every sentence (`chronicle/core/cite.py`) and repairs or drops failures.
- Synthesizes narration with edge-tts; if TTS is unavailable it writes a silent track and still finishes.
- Emits one self-contained folder: inline CSS/JS, no CDN, no external font, no network request at view time.
- Shows the evidence: commit list, per-file diff stats, highlighted diff excerpts, and clickable citation chips.
- Supports `--since TAG` for release mode (narrate only what changed since a tag).
## Quick start

```bash
cd chronicle
python3 -m venv .venv
./.venv/bin/pip install -e .
./.venv/bin/chronicle build --repo . --out chronicle-out --lang en
xdg-open chronicle-out/index.html
```

No install? Run it as a module:

```bash
./.venv/bin/python -m chronicle build --repo /path/to/repo --out /tmp/book --lang ja
```

Deterministic / offline mode (no LLM, no audio):

```bash
./.venv/bin/python -m chronicle build --repo . --out /tmp/book --no-llm --no-audio
```

Release mode:

```bash
./.venv/bin/python -m chronicle build --repo . --since v0.1.0 --out release/
```

## Architecture

```text
  git repository
        |
        v
  core/gitlog.py --- commits, files, numstat, issue refs, diff excerpts
        |
        v
  core/cluster.py -- chapters (conventional type/scope or Jaccard merge)
        |
        v
  summarize.py ----- two sentences per chapter
     /        \
    v          v
 deterministic  llm.py (OpenAI-compatible /chat/completions)
    \          /
     v        v
  core/cite.py ---- citation contract: inspect -> repair -> drop -> fallback
        |
        v
  audio.py --------- edge-tts mp3, silent wav fallback
        |
        v
  html.py ---------- single index.html (inline CSS/JS) + audio/ + chronicle.json
```

Every stage is a plain Python module with no framework dependency. `build.py` wires them together and writes a JSON-serializable payload that the HTML renderer consumes.

## The citation contract

A sentence is allowed into the player only if it contains at least one **known** citation:

1. **Commit SHA** - 7 to 40 hex characters that prefix a commit in the chapter. All-digit strings are rejected so dates and version numbers are not mistaken for SHAs.
2. **File path** - a path that appears in the chapter file list, with a real-looking extension (`src/core/parser.py`).
3. **Issue reference** - `#123` where 123 is present in a commit message in the chapter.

If a sentence cites something unknown (`deadbeef`, `src/imaginary.py`) the validator reports `unknown-citation` and drops it. If it cites nothing it reports `no-citation` and drops it. The summarizer asks the model once to repair the rejected sentence; if the repair still fails, the sentence is discarded. If fewer than two sentences survive, Chronicle fills the gap with the deterministic diff-stat sentences, so a chapter is never empty and never uncited.

Example of a valid deterministic sentence:

```text
Chapter 2 gathers 3 commits between 2026-11-21 and 2026-11-22 that touched src/core/cite.py (+120/-8), and its dominant intent is fix: validator rejects unknown citations (starting at 4f2a9c1).
```

The generated HTML annotates each citation as a chip; clicking a SHA scrolls to the commit, a path scrolls to the file row, an issue scrolls to the evidence block.

## Output layout

```text
chronicle-out/
  index.html          self-contained player (inline CSS + JS)
  chronicle.json      the full payload: chapters, sentences, citations, diffs, meta
  audio/
    chapter-01.mp3    narration (or .wav silence when TTS fails)
    chapter-02.mp3
```

## CLI

```text
chronicle build --repo PATH [--since REF] [--out DIR] [--lang ja|en]
                [--similarity 0.34] [--max-commits 8] [--no-audio] [--no-llm] [--json] [-q]
chronicle doctor
```

`doctor` prints which optional pieces are present: python, git, ffprobe, edge-tts, and the LLM backend.

## LLM backend

Chronicle speaks the OpenAI chat-completions shape and nothing else, so any compatible endpoint works:

```text
export CHRONICLE_LLM=openai-compat
export OPENAI_BASE_URL=http://127.0.0.1:8795/v1
export OPENAI_API_KEY=dummy
export CHRONICLE_MODEL=gpt-4o-mini        # optional
chronicle build --repo . --out chronicle-out
```

Without `OPENAI_API_KEY` the backend is `none` and the deterministic engine is used automatically. LLM errors are recorded per chapter and never abort the build; the deterministic sentences remain the floor.

## Audio

Narration uses edge-tts (`ja-JP-NanamiNeural`, `en-US-AriaNeural`). If synthesis fails, `audio.py` writes a silent WAV of a sensible duration and the player still works. The text is always present, so the demo can run with sound off.

## Tests

```bash
./.venv/bin/python -m pytest -q
```

The suite covers: citation parsing and the enforcement gate (no citation / unknown citation always dropped), clustering determinism and similarity merging, `--since` filtering, diff excerpts, and an end-to-end build that asserts the HTML has zero external `http(s)://` references and that every shipped sentence passes the contract.

## Demo artifacts

- `demo/` - this repository narrated in English, with audio.
- `demo-ja/` - the same story in Japanese.

Open `demo/index.html` directly from disk; it makes no network requests.

## Design notes

- Deterministic first, model second. The fallback is not a stub: it produces the same two-sentence shape from real diff stats and real SHAs.
- The validator owns the truth, not the prompt. A model cannot talk its way past an unknown SHA.
- Zero runtime dependencies outside the standard library; edge-tts is optional.
- The player is a single file plus audio; it can be zipped, emailed, or attached to a release.

## Limits

- Local git only; it does not call the GitHub API or read issues from a tracker. Issue citations come from `#N` references in commit messages.
- Conventional commits get the cleanest chapters; messy histories fall back to file-overlap clustering.
- The LLM path is exercised with a fake client in tests; the public demo runs deterministically.