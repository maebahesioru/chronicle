# Chronicle — hear why your code exists

**Tagline:** Hear why your code exists.

**Track:** AI, Agentic Systems, Cybersecurity, and Dev Tools

**Built from scratch during GenHacks.** The first commit in this repository is dated 2026-11-21; no pre-existing project was reused.

## Inspiration

Every repository remembers *what* changed. Almost none remember *why*. A commit message says "retry parser on empty input"; six months later nobody can tell whether that was a bug fix, a customer escalation, or a temporary hack that became permanent. Changelogs summarize diffs, and AI-generated changelogs confidently invent motivations that never existed.

We wanted the opposite: a tool that is allowed to sound less clever, but is never allowed to make up a reason. Chronicle turns a git history into chapters you can listen to on a walk, and every sentence it speaks has to point at a real commit SHA, a real file path, or a real issue reference. If it cannot cite, it does not ship the sentence.

## What it does

```
chronicle build --repo PATH [--since TAG] [--out DIR] [--lang ja|en]
```

1. Reads `git log` from the repository (oldest first), including changed files, additions/deletions, subjects and bodies.
2. Clusters commits into chapters. Conventional Commits type/scope wins when present; otherwise commits are grouped by file-set similarity (Jaccard), so "the parser work" becomes one chapter even with inconsistent messages.
3. Produces exactly two "why" sentences per chapter. The first sentence fixes the span, size and dominant intent; the second names the heaviest file and the trail between commits.
4. **Enforces the citation contract.** Every generated sentence must contain a citation that exists in that chapter's evidence: a commit SHA, a repository file path, or an issue reference. Sentences with no citation, or with a fabricated one, are dropped; the LLM gets one repair attempt; if it still fails, Chronicle falls back to its deterministic summary.
5. Narrates each chapter with edge-tts (English or Japanese voice). If TTS fails, the build continues with silence and text.
6. Writes a single self-contained folder: `index.html` with inline CSS/JS, embedded JSON, local audio files, chapter list, play-all, citation chips, and diff excerpts. No CDN, no external font, no runtime network request.
7. `--since` is the release mode: only commits after a tag/SHA are built, so a release page can cover just the work since the last version.

If no API key is configured, Chronicle runs entirely in deterministic mode. The demo submitted with this project was built that way.

## How we built it

```
git log ──► core/gitlog.py ──► core/model.py ──► core/cluster.py
                                                      │
                                                      ▼
                                      summarize.py (LLM optional)
                                                      │
                                                      ▼
                                   core/cite.py  ◄── evidence
                                   validator / repair / fallback
                                                      │
                        ┌─────────────────────────────┴────────────┐
                        ▼                                          ▼
                  audio.py (edge-tts)                       html.py (inline)
                        │                                          │
                        └──────────────► demo/index.html ◄─────────┘
```

- **core/gitlog.py** — read-only git plumbing: `git log --reverse --no-merges --no-renames`, file stats, `git show` diff excerpts, tag/SHA resolution for `--since`.
- **core/model.py** — typed `Commit` and `Chapter`; Conventional Commits parsing; per-path stat aggregation; chapter titles that stay readable even when messages are not conventional.
- **core/cluster.py** — deterministic clustering: `(type, scope)` buckets first, then greedy file-overlap merging above a similarity threshold, then splitting into at most eight commits per chapter.
- **core/cite.py** — the contract. Extracts SHA-like tokens (7–40 hex chars, at least one letter and one digit), repository paths, and `#123` references; verifies each sentence against the chapter evidence; returns a structured verdict; `enforce()` drops, repairs and reports what happened.
- **summarize.py** — deterministic two-sentence summary built purely from diff stats, plus an optional LLM path with a repair loop and a mixed fallback when only one sentence survives.
- **llm.py** — small OpenAI-compatible client (`/chat/completions`) configured by environment variables. No SDK, no vendor lock-in.
- **audio.py** — runs `edge-tts` as a subprocess, probes duration with `ffprobe`, and writes a silent WAV when TTS is unavailable.
- **html.py** — one Python template with inline CSS and JavaScript. It embeds the whole payload as JSON, renders citation chips as internal anchors, and tab-switches between the "why" text, evidence, and diff.
- **cli.py** — `build` and `doctor`; `doctor` reports Python, git, ffprobe, edge-tts and LLM configuration.

The test suite is 26 pytest tests. It covers the citation contract (a sentence with no citation must be rejected; a fabricated SHA must be rejected), clamping of commit ranges, deterministic clustering, `--since`, HTML self-containment (zero `http://` or `https://` references), and an end-to-end build with a deliberately hallucinating fake LLM.

## Challenges

**Making the validator strict without making it stupid.** Our first SHA regex accepted dates and version numbers. We required at least one hex letter and one digit. That fixed the false positives, then produced a real false negative: one commit in this repository has the all-digit SHA `7616734`. The validator correctly refused to treat it as a SHA, which meant the deterministic first sentence had no citation and was dropped. We did not weaken the validator; we made the deterministic sentence cite the heaviest file path as well. The demo now reports zero dropped sentences.

**Self-contained means self-contained.** The player must work from a folder with no network. But citations look like URLs, and a naive page would include external links or fonts. The renderer defangs URL-shaped text (inserting a zero-width space after the scheme) so the HTML contains exactly zero `http://`/`https://` substrings, while still showing paths and SHAs as text.

**Trusting an LLM you cannot call.** The shared OpenAI-compatible relay returned a free-usage-limit error during development. Rather than fake a demo, we kept deterministic mode as the shipped path and wrote a fake LLM client in the tests that deliberately invents a commit and then repairs itself. The LLM integration is real code, tested at the HTTP-shaped boundary; the submitted demo does not claim LLM-written prose.

**Keeping a build under control.** TTS is the slowest and least reliable stage. Each chapter has a deadline; a failed or slow synthesis becomes a silent track instead of failing the build. Both language builds finish well inside the two-minute limit.

## Accomplishments

- A real five-chapter tour generated from this repository's own five commits, in English and Japanese.
- Ten narrated MP3 files (five per language), all produced by edge-tts in the verification run.
- **Zero dropped sentences** in both demo builds, and **zero external HTTP references** in both HTML files.
- 26 passing tests, including the adversarial fake-LLM test.
- `--since ed8d397` produced a four-chapter release build with no audio and no external references.
- No paid API, no account creation, no CDN, no database.

## What we learned

- A provenance requirement changes generation, not just validation. Once a sentence must cite something, the model stops writing generic "improved architecture" prose and starts naming the file it actually changed.
- The deterministic fallback is not a toy. It is the reason the tool still produces a complete, honest demo when the LLM quota is gone.
- Negative tests matter as much as positive ones: "no external URL" and "the rejected sentence never appears in the HTML" caught real leaks.
- Clustering on a five-commit repository is a stress test in the other direction: every commit becomes its own chapter. Falling back to the commit subject for titles made the output readable without pretending the commits were conventional.

## What's next

- Fetch GitHub/GitLab issue bodies as first-class evidence (today issue references are recognized, but the body is not fetched).
- Let a reviewer merge or split chapters in the player, with the decision stored next to the release.
- Add embedding-based grouping for large, messy histories.
- Ship a GitHub Action that publishes an audio tour for every release tag.
- More voices and a transcript export for accessibility.

## Libraries, APIs and AI tools used (complete list)

**Runtime**
- Python 3.10+ standard library only: `argparse`, `dataclasses`, `datetime`, `html`, `importlib.util`, `json`, `os`, `pathlib`, `re`, `shutil`, `subprocess`, `sys`, `time`, `urllib.request`, `urllib.error`, `wave`.
- **git** command-line client (read-only: `log`, `show`, `rev-parse`).
- **edge-tts** Python package, which calls Microsoft Edge's online text-to-speech service. Voices used: `en-US-AriaNeural` and `ja-JP-NanamiNeural`.
- **ffprobe** from FFmpeg, used only to measure generated audio duration.
- **OpenAI-compatible Chat Completions API** (optional). Any endpoint that implements `/v1/chat/completions`; configured through `CHRONICLE_LLM`, `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `CHRONICLE_MODEL`. The default is a local relay at `http://127.0.0.1:8795/v1`. The submitted demo did not call it.
- **HTML5, CSS, vanilla JavaScript** — no framework, no bundler, no CDN, no external font.

**Development and testing**
- **pytest** — test runner only, not a runtime dependency.
- **DeepSeek Harness coding agent (deepseek-v4.1-flash)** — AI coding agent used to write, test and document this project. It is not part of the shipped software.

No paid APIs, cloud accounts, databases, or third-party hosted services are required to run Chronicle. edge-tts is the only network service used by the submitted demo.

## Built with

python, git, edge-tts, ffprobe, openai-api, html5, css3, javascript, pytest
