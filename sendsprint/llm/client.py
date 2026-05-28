"""Provider-agnostic LLM client.

Supports Anthropic, OpenAI, Google (Gemini), Groq, and Ollama via REST.
SDK packages are optional - the client falls back to httpx for every provider.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any, Literal, cast

import httpx

from sendsprint.utils.cache import LruTtlCache
from sendsprint.utils.json import dumps_json_bytes, loads_json

logger = logging.getLogger(__name__)

Provider = Literal["anthropic", "openai", "google", "groq", "ollama"]

DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-opus-4-7",
    "openai": "gpt-4o",
    "google": "gemini-2.0-flash",
    "groq": "llama-3.3-70b-versatile",
    "ollama": "llama3.1",
}

_CACHE_MISS = object()
_DEFAULT_COMPLETION_CACHE = LruTtlCache[str, str](
    maxsize=int(os.getenv("SENDSPRINT_LLM_CACHE_SIZE", "128")),
    ttl_s=float(os.getenv("SENDSPRINT_LLM_CACHE_TTL_S", "900")),
)


class LlmError(RuntimeError):
    """Raised when an LLM call fails or no provider is configured."""


class LlmClient:
    """Single entry point ``LlmClient().complete(prompt)``.

    Provider is picked from the ``provider`` argument or the ``LLM_PROVIDER``
    env var (default: ``anthropic``). API key comes from the provider-specific
    env var. The underlying httpx client is kept for the lifetime of this object,
    so repeated LLM calls reuse keep-alive connections instead of recreating a
    TCP/TLS connection for every prompt.
    """

    def __init__(
        self,
        provider: Provider | None = None,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        *,
        http_client: httpx.Client | None = None,
        max_connections: int = 20,
        max_keepalive_connections: int = 10,
        cache_enabled: bool | None = None,
        completion_cache: LruTtlCache[str, str] | None = None,
    ) -> None:
        provider_value = (provider or os.getenv("LLM_PROVIDER") or "anthropic").lower()
        self.provider = cast(Provider, provider_value)
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(self.provider, "")
        self.api_key = api_key or self._resolve_api_key()
        self.base_url = base_url or self._resolve_base_url()
        self.timeout = timeout
        self.cache_enabled = _env_flag("SENDSPRINT_LLM_CACHE", True) if cache_enabled is None else cache_enabled
        self._completion_cache = completion_cache or _DEFAULT_COMPLETION_CACHE
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.Client(
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
            ),
        )

    def complete(self, prompt: str, system: str | None = None, max_tokens: int = 1024) -> str:
        """Complete a prompt, reusing HTTP connections and memoizing identical calls."""
        cache_key = self._cache_key(prompt, system, max_tokens)
        if self.cache_enabled:
            cached = self._completion_cache.get(cache_key, _CACHE_MISS)
            if cached is not _CACHE_MISS:
                return cast(str, cached)

        result = self._complete_uncached(prompt, system, max_tokens)
        if self.cache_enabled:
            self._completion_cache.set(cache_key, result)
        return result

    def close(self) -> None:
        """Close the owned HTTP client and its pooled connections."""
        if self._owns_http_client:
            self._http.close()

    def __enter__(self) -> LlmClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _complete_uncached(self, prompt: str, system: str | None, max_tokens: int) -> str:
        if self.provider == "anthropic":
            return self._call_anthropic(prompt, system, max_tokens)
        if self.provider == "openai":
            return self._call_openai(prompt, system, max_tokens)
        if self.provider == "google":
            return self._call_google(prompt, system, max_tokens)
        if self.provider == "groq":
            return self._call_groq(prompt, system, max_tokens)
        if self.provider == "ollama":
            return self._call_ollama(prompt, system, max_tokens)
        raise LlmError(f"unknown provider: {self.provider}")

    def _resolve_api_key(self) -> str:
        env_map = {
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "ollama": "",
        }
        var = env_map.get(self.provider, "")
        return os.getenv(var, "") if var else ""

    def _resolve_base_url(self) -> str:
        defaults = {
            "anthropic": "https://api.anthropic.com",
            "openai": "https://api.openai.com",
            "google": "https://generativelanguage.googleapis.com",
            "groq": "https://api.groq.com/openai",
            "ollama": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        }
        return defaults.get(self.provider, "")

    def _call_anthropic(self, prompt: str, system: str | None, max_tokens: int) -> str:
        if not self.api_key:
            raise LlmError("ANTHROPIC_API_KEY not set")
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        data = self._post_json(
            f"{self.base_url}/v1/messages",
            body,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
        )
        return "".join(block.get("text", "") for block in data.get("content", []))

    def _call_openai(self, prompt: str, system: str | None, max_tokens: int) -> str:
        return self._call_openai_compatible(prompt, system, max_tokens, self.api_key, self.base_url)

    def _call_groq(self, prompt: str, system: str | None, max_tokens: int) -> str:
        return self._call_openai_compatible(prompt, system, max_tokens, self.api_key, self.base_url)

    def _call_openai_compatible(
        self, prompt: str, system: str | None, max_tokens: int, key: str, base: str
    ) -> str:
        if not key:
            raise LlmError(f"API key for {self.provider} not set")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = {"model": self.model, "messages": messages, "max_tokens": max_tokens}
        data = self._post_json(
            f"{base}/v1/chat/completions",
            body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        choices = data.get("choices", [])
        if not choices:
            return ""
        return choices[0].get("message", {}).get("content", "")

    def _call_google(self, prompt: str, system: str | None, max_tokens: int) -> str:
        if not self.api_key:
            raise LlmError("GOOGLE_API_KEY not set")
        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens},
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        data = self._post_json(url, body, headers={"Content-Type": "application/json"})
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)

    def _call_ollama(self, prompt: str, system: str | None, max_tokens: int) -> str:
        body: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens},
        }
        if system:
            body["system"] = system
        data = self._post_json(f"{self.base_url}/api/generate", body)
        return data.get("response", "")

    def _post_json(
        self,
        url: str,
        body: dict[str, Any],
        *,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        response = self._http.post(
            url,
            content=dumps_json_bytes(body, default=str),
            headers=request_headers,
        )
        response.raise_for_status()
        payload = getattr(response, "content", b"") or getattr(response, "text", "")
        data = loads_json(payload)
        return data if isinstance(data, dict) else {}

    def _cache_key(self, prompt: str, system: str | None, max_tokens: int) -> str:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "prompt": prompt,
            "system": system,
            "max_tokens": max_tokens,
        }
        encoded = dumps_json_bytes(payload, sort_keys=True, default=str)
        return hashlib.blake2b(encoded, digest_size=16).hexdigest()


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}
