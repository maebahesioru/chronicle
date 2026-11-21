"""Pluggable language-model backend for the chapter summaries.

The default backend does not exist: Chronicle runs to completion with zero
network access. Setting CHRONICLE_LLM=openai-compat (or just providing
OPENAI_API_KEY) switches to any OpenAI-compatible chat-completions endpoint,
including a local relay such as http://127.0.0.1:8795/v1.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

DEFAULT_BASE_URL = "http://127.0.0.1:8795/v1"
DEFAULT_MODEL = "gpt-4o-mini"


class LLMError(RuntimeError):
    """Raised when the configured backend cannot answer."""


@dataclass
class LLMConfig:
    backend: str = "none"
    base_url: str = DEFAULT_BASE_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    timeout: float = 40.0

    @property
    def available(self) -> bool:
        return self.backend == "openai-compat" and bool(self.api_key)

    def describe(self) -> str:
        if self.backend != "openai-compat":
            return "deterministic (no LLM configured)"
        if not self.api_key:
            return "deterministic (CHRONICLE_LLM=openai-compat but OPENAI_API_KEY is empty)"
        return "openai-compat model=%s base_url=%s" % (self.model, self.base_url)


def config_from_env(env: dict[str, str] | None = None) -> LLMConfig:
    env = dict(os.environ if env is None else env)
    backend = (env.get("CHRONICLE_LLM") or "").strip().lower()
    api_key = (env.get("OPENAI_API_KEY") or "").strip()
    base_url = (env.get("OPENAI_BASE_URL") or DEFAULT_BASE_URL).strip()
    model = (env.get("CHRONICLE_MODEL") or env.get("OPENAI_MODEL") or DEFAULT_MODEL).strip()
    try:
        timeout = float(env.get("CHRONICLE_LLM_TIMEOUT") or 40.0)
    except ValueError:
        timeout = 40.0
    if not backend:
        backend = "openai-compat" if api_key else "none"
    if backend in ("none", "off", "deterministic", "fallback"):
        backend = "none"
    return LLMConfig(
        backend=backend,
        base_url=base_url.rstrip("/"),
        api_key=api_key,
        model=model,
        timeout=timeout,
    )


class OpenAICompatClient:
    """Minimal chat-completions client (stdlib urllib, no SDK)."""

    name = "openai-compat"

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @property
    def available(self) -> bool:
        return self.config.available

    def complete(self, system: str, user: str, max_tokens: int = 500) -> str:
        if not self.available:
            raise LLMError("LLM backend is not configured")
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": False,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.config.base_url + "/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + self.config.api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout) as response:
                raw = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise LLMError("HTTP %s from %s: %s" % (exc.code, self.config.base_url, detail)) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError("cannot reach %s: %s" % (self.config.base_url, exc)) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LLMError("backend returned non-JSON: %s" % raw[:200]) from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("unexpected response shape: %s" % raw[:200]) from exc
        return (content or "").strip()


def make_client(config: LLMConfig | None = None):
    config = config or config_from_env()
    if config.available:
        return OpenAICompatClient(config)
    return None
