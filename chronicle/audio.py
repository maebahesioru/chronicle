"""Narration: chapter summaries to MP3 via edge-tts, with a silent fallback.

edge-tts talks to Microsoft's public speech endpoint. It is optional on
purpose: when it is missing, offline, or rate limited, Chronicle still writes
a complete player. The fallback is REAL silence (a valid audio file of the
expected length), not a broken reference, so the offline folder never points
at a missing asset.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass

VOICES = {
    "ja": os.environ.get("CHRONICLE_VOICE_JA", "ja-JP-NanamiNeural"),
    "en": os.environ.get("CHRONICLE_VOICE_EN", "en-US-AriaNeural"),
}

SILENT_ENGINE = "silence"


@dataclass
class AudioResult:
    ok: bool
    path: str | None = None
    engine: str = "none"
    bytes: int = 0
    duration_s: float | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "path": self.path,
            "engine": self.engine,
            "bytes": self.bytes,
            "duration_s": self.duration_s,
            "error": self.error,
        }


def edge_tts_available() -> bool:
    return importlib.util.find_spec("edge_tts") is not None


def voice_for(lang: str) -> str:
    return VOICES.get("ja" if str(lang).startswith("ja") else "en", VOICES["en"])


def _probe_duration(path: str) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return round(float(proc.stdout.strip()), 2)
    except ValueError:
        return None


def synthesize_mp3(text: str, out_path: str, lang: str = "en", voice: str | None = None, timeout: int = 45) -> AudioResult:
    """Render one chapter to MP3 with edge-tts. Raises nothing."""
    text = (text or "").strip()
    if not text:
        return AudioResult(ok=False, error="empty text")
    if not edge_tts_available():
        return AudioResult(ok=False, error="edge_tts is not installed in this interpreter")

    voice = voice or voice_for(lang)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    if os.path.exists(out_path):
        os.unlink(out_path)
    command = [
        sys.executable,
        "-m",
        "edge_tts",
        "--voice",
        voice,
        "--text",
        text,
        "--write-media",
        out_path,
        "--no-progress",
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return AudioResult(ok=False, engine="edge-tts", error="edge-tts timed out after %ss" % timeout)
    except OSError as exc:
        return AudioResult(ok=False, engine="edge-tts", error="cannot launch edge-tts: %s" % exc)
    if proc.returncode != 0 or not os.path.exists(out_path):
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return AudioResult(
            ok=False,
            engine="edge-tts",
            error="edge-tts failed: %s" % (detail[-1] if detail else "no output"),
        )
    size = os.path.getsize(out_path)
    if size == 0:
        os.unlink(out_path)
        return AudioResult(ok=False, engine="edge-tts", error="edge-tts wrote an empty file")
    return AudioResult(
        ok=True,
        path=out_path,
        engine="edge-tts:" + voice,
        bytes=size,
        duration_s=_probe_duration(out_path),
    )


def write_silence(out_path: str, seconds: float = 3.0, sample_rate: int = 16000) -> AudioResult:
    """Write a valid silent WAV so a failed narration still has a real asset."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    frames = max(1, int(seconds * sample_rate))
    try:
        with wave.open(out_path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(sample_rate)
            handle.writeframes(b"\x00\x00" * frames)
    except OSError as exc:
        return AudioResult(ok=False, error="cannot write silence: %s" % exc)
    return AudioResult(
        ok=True,
        path=out_path,
        engine=SILENT_ENGINE,
        bytes=os.path.getsize(out_path),
        duration_s=round(seconds, 2),
    )


def narrate(text: str, out_path: str, lang: str = "en", allow_tts: bool = True, timeout: int = 45) -> AudioResult:
    """Try edge-tts, fall back to a silent WAV of similar length."""
    if allow_tts:
        result = synthesize_mp3(text, out_path, lang=lang, timeout=timeout)
        if result.ok:
            return result
        error = result.error
    else:
        error = "tts disabled"
    seconds = max(2.0, min(30.0, len(text or "") / 14.0))
    silent_path = os.path.splitext(out_path)[0] + ".wav"
    silent = write_silence(silent_path, seconds=seconds)
    silent.error = error
    return silent
