"""Unified LLM abstraction for Ollama and Anthropic."""

import json
import os
from enum import Enum


class Provider(str, Enum):
    OLLAMA = "ollama"
    ANTHROPIC = "anthropic"


DEFAULT_MODELS = {
    Provider.ANTHROPIC: "claude-haiku-4-5-20251001",
}


def llm_complete(
    prompt: str,
    system: str = "",
    provider: Provider = Provider.OLLAMA,
    model: str | None = None,
) -> str:
    """Send a prompt to an LLM and return the text response.

    Tries the requested provider first. Raises RuntimeError if unavailable.
    """
    model = model or DEFAULT_MODELS.get(provider) or _default_ollama_model()
    if provider == Provider.OLLAMA:
        return _ollama_complete(prompt, system, model)
    return _anthropic_complete(prompt, system, model)


def detect_provider() -> Provider | None:
    """Return the best available provider, or None."""
    if _ollama_available():
        return Provider.OLLAMA
    if os.environ.get("ANTHROPIC_API_KEY"):
        return Provider.ANTHROPIC
    return None


def _default_ollama_model() -> str:
    try:
        import httpx
        r = httpx.get(f"{_ollama_host()}/api/tags", timeout=3)
        models = r.json().get("models", [])
        if models:
            return models[0]["name"]
    except Exception:
        pass
    return "llama3.2"


def _ollama_available() -> bool:
    try:
        import httpx
        r = httpx.get(
            f"{_ollama_host()}/api/tags",
            timeout=3,
        )
        if r.status_code != 200:
            return False
        models = r.json().get("models", [])
        return len(models) > 0
    except Exception:
        return False


def _ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def _ollama_complete(prompt: str, system: str, model: str) -> str:
    import httpx

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    r = httpx.post(
        f"{_ollama_host()}/api/chat",
        json={"model": model, "messages": messages, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def _anthropic_complete(prompt: str, system: str, model: str) -> str:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Set it or install Ollama for local LLM support."
        )

    from anthropic import Anthropic

    client = Anthropic()
    kwargs: dict = {
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    return response.content[0].text
