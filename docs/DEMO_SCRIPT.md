# Chronicle — 2 minute demo script

Target length: **120 seconds** (hard cap 180 s for Devpost). Record at 1080p, 30 fps.
All commands run from the repository root. The built `demo/` and `demo-ja/` folders are committed, so the recording does not depend on the network.

## Before recording

1. `cd .../chronicle`
2. `./.venv/bin/python -m chronicle doctor` — leave the terminal scrolled so the audience briefly sees the environment check.
3. Close extra tabs. Set the browser zoom to 110% so citation chips are readable.
4. Check audio output. The chapter audio is 42–46 s per chapter in English; use at most 15 s of any one track.

## Storyboard

### 0:00–0:08 — Cold open: the missing "why"

**Screen:** terminal, full screen.

```
git log --oneline --reverse
```

Five lines appear: `core:` … `player:` …

**VO:** "This is everything a git history usually tells you: what changed. It almost never tells you why."

**Caption:** what changed ≠ why

### 0:08–0:20 — Build the tour

**Screen:** same terminal.

```
./.venv/bin/python -m chronicle build --repo . --out demo --lang en
```

Let the output land, then point at `chapters 5 (5 commits)`, `engine deterministic mode (no API key)`, and `dropped 0 sentence(s) without valid citations`. The full run with audio takes about 10 s; speed up the wait 3–4× in the edit if needed.

**VO:** "Chronicle reads the history, clusters the commits into chapters, and writes two sentences of why per chapter. No API key is configured, so it runs in deterministic mode. That is a feature, not a fallback."

**Caption:** 5 chapters · 0 uncited sentences · no API key

### 0:20–0:30 — One folder, one player

**Screen:** open `demo/index.html` (double-clicking the file is fine; no server is required).

Show the header, the chapter list, and the **play all** button.

**VO:** "The output is one folder: inline CSS, inline JavaScript, local audio. No CDN, no external font, no runtime network call."

**Caption:** self-contained folder · zero external HTTP references

### 0:30–0:46 — Chapter one: listen and inspect

**Screen:** click chapter 1, press play. While the voice plays, scroll to the first chapter's sentences and hover the citation chips.

- Chip `22188d1` (SHA) links to the commit block.
- Chip `chronicle/html.py` (path) links to the file row.
- Open the **evidence** tab, then the **diff** tab for one file.

**VO:** "Every sentence carries a citation chip: a real commit, a real file. Click it and you land on the evidence. The audio is reading exactly this text."

**Caption:** every sentence → SHA / path / issue

### 0:46–1:00 — The strict case: an all-digit SHA

**Screen:** chapter 4 (`summaries: deterministic fallback…`). Show the sentence that cites `7616734` **and** `chronicle/summarize.py`.

**VO:** "Commit 7616734 is all digits. The validator refuses to mistake it for a hash, so the sentence also cites the file it touched. The validator was not weakened to make the demo pass; the sentence was made more specific."

**Caption:** strict validator, specific sentence

### 1:00–1:12 — Watch a hallucination die

**Screen:** terminal.

```
./.venv/bin/python examples/validator_demo.py
```

Output appears:

```
cited          accepted  reason=ok
no citation    rejected  reason=no-citation
fabricated     rejected  reason=unknown-citation
               unknown=['src/core/parser.py', 'deadbeef00']
repair loop    kept=1 dropped=0 regenerated=1
no fallback    kept=0 dropped=1 reason=no-citation
```

**VO:** "This is the product. A confident sentence with no citation is rejected. A fabricated SHA and a fabricated path are rejected. One repair is allowed; if the model still cannot cite, the sentence is dropped."

**Caption:** the citation contract, executable

### 1:12–1:20 — Tests

**Screen:** terminal.

```
./.venv/bin/python -m pytest
```

Show the final line: `26 passed`.

**VO:** "Twenty-six tests, including an end-to-end build with a fake LLM that deliberately hallucinates. The rejected sentence is asserted to be absent from the HTML."

**Caption:** 26 passed

### 1:20–1:34 — Release mode

**Screen:** terminal, then browser.

```
./.venv/bin/python -m chronicle build --repo . --since ed8d397 --out release --no-audio
```

Point at `chapters 4 (4 commits)`. Open `release/index.html` briefly: only the last four chapters exist.

**VO:** "Release mode takes a tag or a SHA. This build covers only the work after ed8d397: four chapters, no audio, still zero external references. That is the page you attach to a release."

**Caption:** --since TAG → only this release

### 1:34–1:46 — Japanese

**Screen:** open `demo-ja/index.html`, click chapter 1, play ~8 s.

**VO:** "The same history, narrated in Japanese. The deterministic summaries are localized too, not machine-translated after the fact."

**Caption:** ja-JP-NanamiNeural · same evidence

### 1:46–2:00 — Close

**Screen:** terminal.

```
grep -Eo 'https?://' demo/index.html | wc -l
du -sh demo
```

Output: `0` and `1.4M`.

Cut to a title card: **Chronicle — hear why your code exists.** Command line beneath:
`chronicle build --repo PATH --out tour --lang en`

**VO:** "One folder, zero CDNs, zero invented citations. Chronicle: hear why your code exists."

**Caption:** chronicle build --repo PATH

## Editing notes

- Keep the terminal font at 18 pt or larger; the citation output is the proof, so do not shrink it.
- Do not fake the LLM: the submitted demo is deterministic, and the video says so.
- If TTS audio is not available while recording, the silent build still completes; do not claim audio in that take.
- Trim the ~10 s build to ~5 s with a 2–3× speed ramp; keep the final three summary lines readable.
- End on the `grep` result (0) for at least 2 seconds. It is the fastest proof of self-containment.
