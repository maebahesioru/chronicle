# Verification log — Chronicle

- Date: 2026-11-21 (JST)
- Working tree: `/home/maebahesioru/ダウンロード/sushi_money_research/実行/210_hackathons/genhacks/chronicle`
- Python: 3.14.9, venv at `.venv` (pytest 9.2.0)
- Git HEAD checked: `22188d1 player: offline HTML tour with narrated audio`
- History used for the demo: 5 commits, first one `ed8d397` at 2026-11-21T12:20:00+09:00
- Everything below was executed in this working tree. Git was only read, never written.

## 0. Source history

Command:

```bash
git log --reverse --format='%h %ad %s' --date=iso-strict
```

Output:

```text
ed8d397 2026-11-21T12:20:00+09:00 core: read a git history into a typed timeline
629c8fb 2026-11-21T12:31:00+09:00 chapters: cluster commits and enforce the citation contract
efabb20 2026-11-21T12:42:00+09:00 cli: chronicle build --repo PATH [--since TAG] [--out DIR] [--lang ja|en]
7616734 2026-11-21T12:52:00+09:00 summaries: deterministic fallback plus any OpenAI-compatible endpoint
22188d1 2026-11-21T13:00:00+09:00 player: offline HTML tour with narrated audio
```

The first commit is after the GenHacks start. No code was imported from an older project.

## 1. Test suite

Command:

```bash
./.venv/bin/python -m pytest
```

Output:

```text
..........................                                               [100%]
26 passed in 1.99s
```

The 26 tests cover:

- the citation contract: a sentence without a citation is rejected; a sentence quoting an unknown SHA/path/issue is rejected; a repair round can replace a bad sentence; with no fallback the chapter keeps 0 sentences;
- deterministic clustering: same input gives the same chapters, conventional type/scope grouping, file-similarity grouping, max-commit splitting;
- `--since`: `v0.1.0` style refs resolve to a SHA and filtering keeps only newer commits; an unknown ref raises `GitError`;
- HTML self-containment: no `http://` or `https://` substring, no `<link rel="stylesheet">`, no external script, inline style/script present;
- a fake LLM that emits one fabricated sentence: the fabricated sentence is dropped, the surviving sentence passes the contract, and the fabricated text does not appear in the HTML.

## 2. Environment doctor

Command:

```bash
./.venv/bin/python -m chronicle doctor
```

Output:

```text
python           3.14.9
git              /usr/bin/git
ffprobe          /usr/bin/ffprobe
edge-tts         available, voice en-US-AriaNeural
llm backend      none (no key: deterministic)
llm base url     http://127.0.0.1:8795/v1
llm model        gpt-4o-mini
cwd is git repo  yes
```

`llm backend none` is expected: no `OPENAI_API_KEY` was set, so the build automatically selected the deterministic summarizer.

## 3. Demo builds

English:

```bash
./.venv/bin/python -m chronicle build --repo . --out demo --lang en
```

Output:

```text
chapters      5 (5 commits)
engine        deterministic mode (no API key)
audio         5 narrated, 0 silent, 0 failed
sources       deterministic=5
dropped       0 sentence(s) without valid citations
elapsed       9.8s
output        demo/index.html
  read 5 commit(s)
  clustered into 5 chapter(s)
  summaries: deterministic=5
  audio 01 edge-tts:en-US-AriaNeural
  audio 02 edge-tts:en-US-AriaNeural
  audio 03 edge-tts:en-US-AriaNeural
  audio 04 edge-tts:en-US-AriaNeural
  audio 05 edge-tts:en-US-AriaNeural
```

Japanese:

```bash
./.venv/bin/python -m chronicle build --repo . --out demo-ja --lang ja
```

Output:

```text
chapters      5 (5 commits)
engine        決定論モード（APIキーなし）
audio         5 narrated, 0 silent, 0 failed
sources       deterministic=5
dropped       0 sentence(s) without valid citations
elapsed       9.7s
output        demo-ja/index.html
  read 5 commit(s)
  clustered into 5 chapter(s)
  summaries: deterministic=5
  audio 01 edge-tts:ja-JP-NanamiNeural
  audio 02 edge-tts:ja-JP-NanamiNeural
  audio 03 edge-tts:ja-JP-NanamiNeural
  audio 04 edge-tts:ja-JP-NanamiNeural
  audio 05 edge-tts:ja-JP-NanamiNeural
```

## 4. Measured artifacts

```text
[demo] index=85701 json=44621 chapters=5 commits=5 dropped=0 engine=deterministic lang=en
  ch01 audio=audio/chapter-01.mp3 bytes=253584 duration=42.26 engine=edge-tts:en-US-AriaNeural
  ch02 audio=audio/chapter-02.mp3 bytes=265248 duration=44.21 engine=edge-tts:en-US-AriaNeural
  ch03 audio=audio/chapter-03.mp3 bytes=262656 duration=43.78 engine=edge-tts:en-US-AriaNeural
  ch04 audio=audio/chapter-04.mp3 bytes=278496 duration=46.42 engine=edge-tts:en-US-AriaNeural
  ch05 audio=audio/chapter-05.mp3 bytes=264672 duration=44.11 engine=edge-tts:en-US-AriaNeural
  audio_total=1324656
[demo-ja] index=87570 json=45841 chapters=5 commits=5 dropped=0 engine=deterministic lang=ja
  ch01 audio=audio/chapter-01.mp3 bytes=300672 duration=50.11 engine=edge-tts:ja-JP-NanamiNeural
  ch02 audio=audio/chapter-02.mp3 bytes=305856 duration=50.98 engine=edge-tts:ja-JP-NanamiNeural
  ch03 audio=audio/chapter-03.mp3 bytes=294480 duration=49.08 engine=edge-tts:ja-JP-NanamiNeural
  ch04 audio=audio/chapter-04.mp3 bytes=332784 duration=55.46 engine=edge-tts:ja-JP-NanamiNeural
  ch05 audio=audio/chapter-05.mp3 bytes=295344 duration=49.22 engine=edge-tts:ja-JP-NanamiNeural
  audio_total=1529136
```

Sizes on disk:

```text
1.4M    demo
1.7M    demo-ja
```

## 5. HTML self-containment audit

Command:

```bash
for f in demo/index.html demo-ja/index.html; do
  printf '%s external=' "$f"; grep -Eo 'https?://' "$f" | wc -l
  printf '  link_stylesheet='; grep -c '<link[^>]*stylesheet' "$f" || true
  printf '  script_src='; grep -c '<script[^>]*src=' "$f" || true
done
```

Output:

```text
demo/index.html external=0
  link_stylesheet=0
  script_src=0
demo-ja/index.html external=0
  link_stylesheet=0
  script_src=0
```

Additional checks: `@import` 0, `url(http` 0 in both files. The pages also contain 1 inline `<style>` and 2 inline `<script>` blocks, and they load `audio/chapter-NN.mp3` from the same folder.

SHA-256 of the final pages:

```text
65eb65bec4d6341351c4a3248be4f8bc90ab9f3ebdcd7349567c70e7654eeb25  demo/index.html
48f6c8a6a034bcd1aa2efab99411647a1137808dbf3fb85d313916124630bf41  demo-ja/index.html
```

## 6. Release mode: `--since`

Command:

```bash
./.venv/bin/python -m chronicle build --repo . --since ed8d397 --out /tmp/chronicle-since-verify --no-audio --no-llm
```

Output:

```text
chapters      4 (4 commits)
engine        deterministic mode (no API key)
audio         0 narrated, 0 silent, 0 failed
sources       deterministic=4
dropped       0 sentence(s) without valid citations
elapsed       0.1s
output        /tmp/chronicle-since-verify/index.html
  since ed8d397 -> ed8d3976d46c
  read 4 commit(s)
  clustered into 4 chapter(s)
  summaries: deterministic=4
```

The resulting `index.html` contained 0 external HTTP references. `chronicle.json` meta was `{'since': 'ed8d397', 'commits': 4, 'chapters': 4, 'dropped': 0, 'lang': 'en'}`. The temporary folder was deleted after the check.

## 7. Citation validator demonstration

Command:

```bash
./.venv/bin/python examples/validator_demo.py
```

Output:

```text
cited          accepted  reason=ok
no citation    rejected  reason=no-citation
fabricated     rejected  reason=unknown-citation
               unknown=['src/core/parser.py', 'deadbeef00']
repair loop    kept=1 dropped=0 regenerated=1
no fallback    kept=0 dropped=1 reason=no-citation
```

This is the segment used at 1:00–1:12 in the demo video. The validator does not trust a generated sentence just because it is fluent; it checks that every cited SHA/path/issue actually exists in that chapter's evidence.

## 8. Browser check of the built player

The folder was served with `python -m http.server 8877 --directory demo` and opened at `http://127.0.0.1:8877/` in the shared browser.

DOM/state read back from the browser:

```text
title=Chronicle — hear why your code exists
chapters=5
data.chapters=5
data.meta.commits=5
data.meta.dropped=0
cite-sha chips=8
cite-path chips=10
play_all button=present
inline style=1 / inline script=2
externalRefs=[]
after clicking the first chapter Play button:
  audio.paused=false
  audio.currentSrc=http://127.0.0.1:8877/audio/chapter-01.mp3
  audio.currentTime=1.917902
  audio.duration=42.264
```

The `audio.currentSrc` is a local URL created by the same server; it is not a reference embedded in `index.html`. The HTML itself has 0 `http(s)` strings.

## 9. LLM backend status (honest result)

No paid API was used. The OpenAI-compatible path is implemented and tested with a fake client, but a live LLM completion could not be demonstrated in this environment:

- The local relay at `http://127.0.0.1:8795/v1` answered `GET /models` with 200.
- `POST /v1/chat/completions` with a dummy bearer token returned HTTP 429 `FreeUsageLimitError`, with `retryAfterSeconds: 72239` in the body.
- Therefore the demo was built in deterministic mode, which is a supported first-class path, not a fallback stub. The validator/repair loop was exercised with a fake LLM in `tests/test_build.py`.

## 10. Not verified

- Live LLM-generated chapters against a real provider (blocked by the 429 above). The code path is covered by the fake-client test only.
- Offline edge-tts failure handling end-to-end. The code writes a silent WAV if TTS fails, and `--no-audio` is exercised, but a forced network failure was not part of this run.
- macOS and Windows. Only Linux with Python 3.14.9 was run.
- GitHub push. That is handled by the Lead; this working tree has no push.

## 11. Reproduce

```bash
./.venv/bin/python -m pytest
./.venv/bin/python -m chronicle build --repo . --out demo --lang en
./.venv/bin/python -m chronicle build --repo . --out demo-ja --lang ja
./.venv/bin/python -m chronicle build --repo . --since ed8d397 --out /tmp/release --no-audio --no-llm
```

