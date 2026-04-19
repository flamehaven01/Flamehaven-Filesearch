"""
LLM Provider abstraction for FLAMEHAVEN FileSearch.

Supported providers:
  gemini           : Google Gemini API (cloud, default)
  openai           : OpenAI ChatGPT API (cloud)
  anthropic        : Anthropic Claude API (cloud)
  ollama           : Local inference via Ollama (Gemma4, Qwen, Kimi, etc.)
  openai_compatible: Any OpenAI-compatible endpoint (vLLM, LM Studio, Kimi API)

Usage::
    from flamehaven_filesearch.engine.llm_providers import create_llm_provider
    provider = create_llm_provider(config)
    answer = provider.generate(prompt, max_tokens=512, temperature=0.5)
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Iterator, Optional

if TYPE_CHECKING:
    from ..config import Config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class AbstractLLMProvider(ABC):
    """Base class for all LLM provider integrations."""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Return generated text, or empty string on failure."""

    @abstractmethod
    def stream(self, prompt: str, max_tokens: int, temperature: float) -> Iterator[str]:
        """Yield text tokens as they arrive."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short identifier used in response metadata and logs."""


# ---------------------------------------------------------------------------
# Cloud providers
# ---------------------------------------------------------------------------


class GeminiProvider(AbstractLLMProvider):
    """Google Gemini API via google-genai SDK (prompt-only, no file_search tool)."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            from google import genai
            from google.genai import types

            self._client = genai.Client(api_key=api_key)
            self._types = types
        except ImportError:
            raise ImportError(
                "google-genai not installed. "
                "Run: pip install flamehaven-filesearch[google]"
            )
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"gemini/{self._model}"

    def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=self._types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                ),
            )
            return resp.text or ""
        except Exception as exc:
            logger.warning("[GeminiProvider] generate failed: %s", exc)
            return ""

    def stream(self, prompt: str, max_tokens: int, temperature: float) -> Iterator[str]:
        for chunk in self._client.models.generate_content_stream(
            model=self._model,
            contents=prompt,
            config=self._types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        ):
            if chunk.text:
                yield chunk.text


class OpenAIProvider(AbstractLLMProvider):
    """OpenAI ChatGPT API or any OpenAI-compatible endpoint.

    Compatible with: OpenAI, vLLM, LM Studio, Kimi (api.moonshot.cn/v1), etc.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: Optional[str] = None,
    ) -> None:
        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, base_url=base_url)
        except ImportError:
            raise ImportError(
                "openai not installed. "
                "Run: pip install flamehaven-filesearch[openai]"
            )
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"openai/{self._model}"

    def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("[OpenAIProvider] generate failed: %s", exc)
            return ""

    def stream(self, prompt: str, max_tokens: int, temperature: float) -> Iterator[str]:
        for chunk in self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True,
        ):
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class AnthropicProvider(AbstractLLMProvider):
    """Anthropic Claude API (claude-3-5-sonnet, claude-opus-4, etc.)."""

    def __init__(self, api_key: str, model: str) -> None:
        try:
            import anthropic

            self._client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError(
                "anthropic not installed. "
                "Run: pip install flamehaven-filesearch[anthropic]"
            )
        self._model = model

    @property
    def provider_name(self) -> str:
        return f"anthropic/{self._model}"

    def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            msg = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text if msg.content else ""
        except Exception as exc:
            logger.warning("[AnthropicProvider] generate failed: %s", exc)
            return ""

    def stream(self, prompt: str, max_tokens: int, temperature: float) -> Iterator[str]:
        with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        ) as s:
            for text in s.text_stream:
                yield text


# ---------------------------------------------------------------------------
# Local provider
# ---------------------------------------------------------------------------


class OllamaProvider(AbstractLLMProvider):
    """Local model inference via Ollama REST API (zero API key required).

    Supported models (install with `ollama pull <model>`):
      gemma4:27b  gemma4:4b   gemma4:2b   (Google Gemma 4 — 128K / 256K ctx)
      qwen2.5:7b  qwen2.5:14b qwen2.5:32b (Alibaba Qwen 2.5)
      mistral     llama3.2    phi4         (and any Ollama-hosted model)

    Requires: Ollama running at base_url (default http://localhost:11434)
    """

    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self._model = model
        self._url = base_url.rstrip("/")

    @property
    def provider_name(self) -> str:
        return f"ollama/{self._model}"

    def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        try:
            import httpx

            resp = httpx.post(
                f"{self._url}/api/generate",
                json={
                    "model": self._model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature,
                    },
                },
                timeout=120.0,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")
        except Exception as exc:
            logger.warning("[OllamaProvider] generate failed: %s", exc)
            return ""

    def stream(self, prompt: str, max_tokens: int, temperature: float) -> Iterator[str]:
        import httpx

        with httpx.stream(
            "POST",
            f"{self._url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            },
            timeout=120.0,
        ) as resp:
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_llm_provider(config: "Config") -> AbstractLLMProvider:
    """Build and return the LLM provider declared in config."""
    p = config.llm_provider.lower()

    if p == "gemini":
        return GeminiProvider(api_key=config.api_key or "", model=config.default_model)

    if p == "openai":
        return OpenAIProvider(
            api_key=config.openai_api_key or "",
            model=config.default_model,
        )

    if p in {"openai_compatible", "kimi", "vllm", "lmstudio"}:
        return OpenAIProvider(
            api_key=config.openai_api_key or "none",
            model=config.default_model,
            base_url=config.openai_base_url,
        )

    if p == "anthropic":
        return AnthropicProvider(
            api_key=config.anthropic_api_key or "",
            model=config.default_model,
        )

    if p == "ollama":
        return OllamaProvider(
            model=config.local_model,
            base_url=config.ollama_base_url,
        )

    raise ValueError(
        f"Unknown llm_provider: '{p}'. "
        "Valid values: gemini, openai, anthropic, ollama, openai_compatible"
    )
