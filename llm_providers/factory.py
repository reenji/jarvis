"""Factory for configured ARGUS LLM providers."""

from __future__ import annotations

import os
from typing import Any, List, Optional

from config.settings import get_settings
from llm_providers.base import BaseLLM
from llm_providers.gemini import GeminiLLM


def _create_single_provider(
    provider_name: str, api_key: str | None, **kwargs: Any
) -> BaseLLM:
    """Create a single LLM provider by name. Raises if provider cannot be created."""
    selected_provider = provider_name.strip().lower()

    if selected_provider == "gemini":
        key = api_key or os.environ.get(
            "ARGUS_LLM_GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "")
        )
        if not key:
            raise ValueError(
                "Gemini API key required. Set ARGUS_LLM_GEMINI_API_KEY "
                "or GEMINI_API_KEY."
            )
        runtime = getattr(get_settings(), "runtime", None)
        retry_max = runtime.reconnect_max_attempts if runtime else 0
        retry_delay = 1.0
        if runtime is not None:
            retry_delay = getattr(
                runtime, "reconnect_backoff_base_delay", 1.0
            )
        return GeminiLLM(api_key=key, max_retries=retry_max, retry_delay=retry_delay, **kwargs)

    if selected_provider == "openai":
        raise NotImplementedError(
            "The OpenAI Realtime provider is not implemented yet."
        )

    if selected_provider == "ollama":
        raise NotImplementedError("The Ollama provider is not implemented yet.")

    raise ValueError(f"Unknown LLM provider: {selected_provider}")


def create_llm_provider(
    provider: str | None = None,
    api_key: str | None = None,
    **kwargs: Any,
) -> BaseLLM:
    """Create a configured provider with optional fallback support.

    Tries the selected provider first, then falls back to configured
    fallback_providers if the primary fails with a transient error.
    """
    settings = get_settings()
    selected_provider = (provider or settings.llm.provider).strip().lower()
    fallbacks: List[str] = getattr(settings.llm, "fallback_providers", []) or []

    # Build ordered list: primary first, then fallbacks
    provider_order: List[str] = [selected_provider] + [
        p.strip().lower() for p in fallbacks if p.strip()
    ]

    last_error: Optional[str] = None

    for i, prov in enumerate(provider_order):
        # Get API key for this provider
        current_key: Optional[str] = api_key
        if prov == "gemini":
            current_key = current_key or settings.llm.gemini_api_key or os.environ.get(
                "ARGUS_LLM_GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", "")
            )
            if not current_key:
                last_error = "Gemini API key required. Set ARGUS_LLM_GEMINI_API_KEY or GEMINI_API_KEY."
                continue
        elif prov == "openai":
            raise NotImplementedError("The OpenAI Realtime provider is not implemented yet.")
        elif prov == "ollama":
            raise NotImplementedError("The Ollama provider is not implemented yet.")
        else:
            last_error = f"Unknown LLM provider: {prov}"
            continue

        try:
            result = _create_single_provider(prov, current_key, **kwargs)
            return result
        except Exception as e:
            last_error = str(e)
            # If this is not the last provider in the list, try the next one
            if i < len(provider_order) - 1:
                continue
            # Last attempt failed; re-raise with context
            raise ValueError(
                f"LLM provider '{prov}' failed after all attempts. "
                f"Last error: {last_error}"
            ) from e

    # Should not reach here, but just in case
    raise ValueError(f"No LLM provider available. Last error: {last_error}")


def get_llm_provider_from_settings(**kwargs: Any) -> BaseLLM:
    """Create the provider selected by ARGUS settings."""
    return create_llm_provider(**kwargs)