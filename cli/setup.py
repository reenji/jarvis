"""Interactive, secret-safe first-run setup for the terminal client."""

from __future__ import annotations

import getpass
import os
import sys
from dataclasses import dataclass
from typing import Callable

from config.settings import get_api_key, get_settings
from config.user_config import (
    UserConfigError,
    get_gemini_key_source,
    load_user_config,
    save_user_config,
    store_gemini_key,
)


@dataclass(frozen=True)
class ApiProbe:
    ok: bool
    message: str


def validate_gemini_key(api_key: str, *, model: str | None = None) -> ApiProbe:
    """Make a minimal bounded request without returning provider error text."""
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=10_000),
        )
        client.models.generate_content(
            model=model or os.environ.get("ARGUS_CLI_MODEL") or get_settings().llm.model,
            contents="Reply with OK.",
            config=types.GenerateContentConfig(max_output_tokens=2, temperature=0),
        )
        return ApiProbe(True, "Gemini API access verified.")
    except Exception as exc:
        status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        class_name = type(exc).__name__.casefold()
        if status in (401, 403):
            return ApiProbe(False, "Gemini rejected the key or this project lacks API access.")
        if status == 429:
            return ApiProbe(False, "Gemini quota or rate limit reached; check quota and billing, then retry.")
        if isinstance(status, int) and status >= 500:
            return ApiProbe(False, f"Gemini service returned HTTP {status}; retry later.")
        if "timeout" in class_name or isinstance(exc, TimeoutError):
            return ApiProbe(False, "Gemini request timed out after 10 seconds; check the network or proxy.")
        if any(token in class_name for token in ("connection", "transport", "network")):
            return ApiProbe(False, "Could not reach Gemini; check the network, DNS, and proxy settings.")
        if isinstance(status, int):
            return ApiProbe(False, f"Gemini request failed with HTTP {status}; check the model and API access.")
        return ApiProbe(False, "Gemini request failed; check network access and the installed Google SDK.")


def _existing_key() -> tuple[str | None, str | None]:
    source = get_gemini_key_source()
    try:
        key = get_api_key()
    except (ValueError, UserConfigError):
        return None, source
    return key, source or "legacy configuration"


def run_setup(
    *,
    input_fn: Callable[[str], str] | None = None,
    secret_input_fn: Callable[[str], str] | None = None,
    api_probe: Callable[[str], ApiProbe] | None = None,
    output: Callable[[str], None] | None = None,
) -> int:
    input_fn = input_fn or input
    secret_input_fn = secret_input_fn or getpass.getpass
    api_probe = api_probe or validate_gemini_key
    output = output or print

    if input_fn is input and not sys.stdin.isatty():
        output("Run `argus setup` in an interactive terminal.")
        return 2

    try:
        config = load_user_config()
    except UserConfigError as exc:
        output(str(exc))
        return 2

    key, source = _existing_key()
    if key:
        output(f"Gemini key found in {source}; validating without displaying it.")
        probe = api_probe(key)
        if not probe.ok:
            output(probe.message)
            if source == "environment":
                output("Update ARGUS_LLM_GEMINI_API_KEY or GEMINI_API_KEY and run setup again.")
                return 1
            key = None

    should_store_key = bool(key and source not in {"environment", "system keyring"})
    if not key:
        try:
            key = secret_input_fn("Gemini API key (input hidden): ").strip()
        except (EOFError, KeyboardInterrupt):
            output("Setup cancelled.")
            return 130
        if not key:
            output("No key entered. Setup was not saved.")
            return 2
        probe = api_probe(key)
        if not probe.ok:
            output(probe.message)
            return 1
        should_store_key = True

    voice_config = config.setdefault("voice", {})
    if not isinstance(voice_config, dict):
        voice_config = {}
        config["voice"] = voice_config
    current_voice = bool(voice_config.get("enabled", False))
    default = "Y/n" if current_voice else "y/N"
    try:
        answer = input_fn(f"Enable optional voice mode? [{default}]: ").strip().casefold()
    except (EOFError, KeyboardInterrupt):
        output("Setup cancelled; the API key was not saved.")
        return 130
    if answer in {"y", "yes", "s", "sim"}:
        voice_config["enabled"] = True
    elif answer in {"n", "no", "nao", "não"}:
        voice_config["enabled"] = False
    else:
        voice_config["enabled"] = current_voice

    try:
        if should_store_key:
            store = store_gemini_key(config, key)
        else:
            store = source or "existing configuration"
        path = save_user_config(config)
    except UserConfigError as exc:
        output(str(exc))
        return 1

    output(f"Setup complete. Gemini key storage: {store}.")
    output(f"Configuration saved at {path}.")
    if voice_config["enabled"]:
        output("Voice preference saved; voice support requires the optional voice phase and dependencies.")
    return 0
