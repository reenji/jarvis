"""LLM Providers package for ARGUS."""

from __future__ import annotations

from llm_providers.base import (
    BaseLLM,
    LLMConfig,
    LLMEvent,
    LLMEventType,
    ToolCall,
    ToolResult,
    LLMProviderError,
    LLMConnectionError,
    LLMAuthenticationError,
    LLMUnsupportedVoiceError,
    LLMTransientError,
)

from llm_providers.gemini import GeminiLLM
from llm_providers.openai import OpenAILLM
from llm_providers.ollama import OllamaLLM
from llm_providers.factory import create_llm_provider, get_llm_provider_from_settings

__all__ = [
    # Base classes
    "BaseLLM",
    "LLMConfig",
    "LLMEvent",
    "LLMEventType",
    "ToolCall",
    "ToolResult",
    "LLMProviderError",
    "LLMConnectionError",
    "LLMAuthenticationError",
    "LLMUnsupportedVoiceError",
    "LLMTransientError",
    # Implementations
    "GeminiLLM",
    "OpenAILLM",
    "OllamaLLM",
    # Factory
    "create_llm_provider",
    "get_llm_provider_from_settings",
]
