"""Central configuration for ARGUS.

Loads from (in order of precedence):
1) Environment variables (prefixed with ARGUS_)
2) config/api_keys.json (legacy)
3) Defaults defined in code
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import List, Optional, Literal

from pydantic import Field, validator
from pydantic_settings import BaseSettings

from config.user_config import get_configured_gemini_key, load_user_config

BASE_DIR = Path(__file__).resolve().parent.parent


class LLMSettings(BaseSettings):
    provider: Literal["gemini", "openai", "ollama"] = "gemini"
    model: str = "gemini-2.5-flash"
    fallback_providers: List[str] = []

    # API keys
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Ollama (stub until Phase 8)
    ollama_host: Optional[str] = None
    ollama_model: Optional[str] = None

    class Config:
        env_prefix = "ARGUS_LLM_"


class VoiceSettings(BaseSettings):
    enabled: bool = False
    name: str = "puck"

    class Config:
        env_prefix = "ARGUS_VOICE_"


class AudioSettings(BaseSettings):
    channels: int = 1
    send_sample_rate: int = 16000
    receive_sample_rate: int = 24000
    chunk_size: int = 1024
    vad_silence_ms: int = 700
    backend: Literal["auto", "sounddevice", "dummy"] = "auto"

    class Config:
        env_prefix = "ARGUS_AUDIO_"


class FeaturesSettings(BaseSettings):
    # empty => enabled tools default is "all built-in tools"
    enabled_tools: List[str] = []
    enabled_plugins: List[str] = []

    class Config:
        env_prefix = "ARGUS_FEATURES_"


class RuntimeSettings(BaseSettings):
    runtime_limit_seconds: Optional[int] = None
    required_unlock_path: Optional[str] = None
    required_unlock_secret: Optional[str] = None

    # Live reconnection/backoff (provider errors)
    # Only applied when the connection error is classified as transient.
    # Backoff is disabled by default to preserve current reconnect timing.
    reconnect_backoff_enabled: bool = False

    # 0 means unlimited retries (matches prior behavior of reconnecting forever)
    reconnect_max_attempts: int = 0

    # Fractional jitter applied on top of the base exponential delay
    reconnect_jitter_ratio: float = 0.15

    # Base delay (seconds) for exponential backoff when reconnect_backoff_enabled
    reconnect_backoff_base_delay: float = 1.0

    class Config:
        env_prefix = "ARGUS_RUNTIME_"


class Settings(BaseSettings):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    features: FeaturesSettings = Field(default_factory=FeaturesSettings)
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    @validator("llm", pre=True, always=True)
    def load_llm_legacy_config(cls, v):  # noqa: N805
        api_keys_path = BASE_DIR / "config" / "api_keys.json"
        legacy: dict = {}
        if api_keys_path.exists():
            try:
                legacy = json.loads(api_keys_path.read_text(encoding="utf-8"))
            except Exception:
                legacy = {}

        if not isinstance(v, dict):
            v = {}

        # Environment remains the highest-precedence source.
        env_gemini_key = os.environ.get("ARGUS_LLM_GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if env_gemini_key:
            v.setdefault("gemini_api_key", env_gemini_key)
        elif v.get("gemini_api_key") is None:
            configured_key = get_configured_gemini_key()
            if configured_key:
                v.setdefault("gemini_api_key", configured_key)
            elif legacy.get("api_key"):
                v.setdefault("gemini_api_key", legacy["api_key"])

        user_config = load_user_config()
        user_llm = user_config.get("llm") or {}
        if isinstance(user_llm, dict):
            if os.environ.get("ARGUS_LLM_MODEL") is None and user_llm.get("model"):
                v.setdefault("model", str(user_llm["model"]))
            if os.environ.get("ARGUS_LLM_PROVIDER") is None and user_llm.get("provider"):
                v.setdefault("provider", str(user_llm["provider"]))

        return v

    @validator("voice", pre=True, always=True)
    def load_voice_legacy_config(cls, v):  # noqa: N805
        api_keys_path = BASE_DIR / "config" / "api_keys.json"
        legacy: dict = {}
        if api_keys_path.exists():
            try:
                legacy = json.loads(api_keys_path.read_text(encoding="utf-8"))
            except Exception:
                legacy = {}

        if not isinstance(v, dict):
            v = {}

        env_voice = os.environ.get("GEMINI_VOICE_NAME")
        user_config = load_user_config()
        user_voice = user_config.get("voice") or {}
        if not isinstance(user_voice, dict):
            user_voice = {}
        if env_voice:
            v.setdefault("name", env_voice)
        elif user_voice.get("name"):
            v.setdefault("name", str(user_voice["name"]))
        elif v.get("name") in (None, "") and legacy.get("voice_name"):
            v.setdefault("name", legacy["voice_name"])

        env_voice_enabled = os.environ.get("ARGUS_VOICE_ENABLED")
        if env_voice_enabled is not None:
            v.setdefault("enabled", env_voice_enabled)
        elif "enabled" in user_voice:
            v.setdefault("enabled", user_voice["enabled"])

        return v

    @validator("runtime", pre=True, always=True)
    def load_runtime_env(cls, v):  # noqa: N805
        # main.py reads these env vars directly today; this bridges that.
        if not isinstance(v, dict):
            v = {}

        runtime_kw = os.environ.get("ARGUS_TRIAL_KEYWORD")
        if runtime_kw:
            runtime_seconds = os.environ.get("ARGUS_RUNTIME_SECONDS", "3600")
            try:
                v.setdefault("runtime_limit_seconds", int(runtime_seconds))
            except Exception:
                pass

        locked_secret = os.environ.get("ARGUS_LOCKED_KEY_SECRET")
        if locked_secret:
            v.setdefault("required_unlock_secret", locked_secret.strip())

        locked_vol = os.environ.get("ARGUS_LOCKED_VOLUME")
        if locked_vol:
            mount_path = f"/Volumes/{locked_vol}/unlock.key"
            v.setdefault("required_unlock_path", mount_path)

        return v


def get_settings() -> Settings:
    return Settings()


# Backwards compatible helpers (used by existing code we refactor later)
def get_api_key() -> str:
    settings = get_settings()
    if not settings.llm.gemini_api_key:
        raise ValueError(
            "GEMINI_API_KEY not set. Set via environment "
            "ARGUS_LLM_GEMINI_API_KEY or GEMINI_API_KEY, "
            "run `argus setup`, or use config/api_keys.json"
        )
    return settings.llm.gemini_api_key


def get_voice_name() -> str:
    return get_settings().voice.name
