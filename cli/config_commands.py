"""Safe user-facing config inspection and preference editing."""

from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any

from config.settings import get_settings
from config.user_config import (
    UserConfigError,
    get_gemini_key_source,
    load_user_config,
    save_user_config,
    user_config_path,
)
from cli.terminal_profile import load_terminal_profile, save_terminal_preference


def show_config(output: Callable[[str], None] = print) -> int:
    try:
        settings = get_settings()
        source = get_gemini_key_source()
    except UserConfigError as exc:
        output(str(exc))
        return 2

    key_status = f"configured ({source or 'legacy source'})" if settings.llm.gemini_api_key else "not configured"
    output(f"Configuration path: {user_config_path()}")
    output(f"Gemini API key: {key_status}; value hidden")
    output(f"LLM model: {os.environ.get('ARGUS_CLI_MODEL') or settings.llm.model}")
    output(f"Voice enabled: {'yes' if settings.voice.enabled else 'no'}")
    output(f"Voice name: {settings.voice.name}")
    from cli.banner import banner_preference

    output(f"Banner: {'enabled' if banner_preference() else 'disabled'}")
    profile = load_terminal_profile()
    output(f"Terminal theme: {profile.theme}")
    output(f"Terminal assistant name: {profile.assistant_name}")
    output(f"Terminal user name: {profile.user_name}")
    return 0


def _parse_value(key: str, value: str) -> Any:
    if key in {"voice.enabled", "banner"}:
        normalized = value.strip().casefold()
        if normalized in {"true", "yes", "on", "1", "sim", "s"}:
            return True
        if normalized in {"false", "no", "off", "0", "nao", "não", "n"}:
            return False
        raise ValueError(f"{key} must be true or false.")
    if key in {"voice.name", "llm.model"}:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 120:
            raise ValueError(f"{key} must contain 1 to 120 characters.")
        return cleaned
    if key == "terminal.theme":
        from cli.terminal_profile import THEMES

        normalized = value.strip().casefold()
        if normalized not in THEMES:
            raise ValueError(f"terminal.theme must be one of: {', '.join(THEMES)}.")
        return normalized
    if key in {"terminal.assistant_name", "terminal.user_name"}:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 32:
            raise ValueError(f"{key} must contain 1 to 32 characters.")
        return cleaned
    if key == "llm.gemini_api_key":
        raise ValueError("Use `argus setup` to enter the Gemini key without exposing it in shell history.")
    raise ValueError(
        "Supported keys: banner, voice.enabled, voice.name, llm.model, "
        "terminal.theme, terminal.assistant_name, terminal.user_name."
    )


def set_config_value(key: str, value: str, output: Callable[[str], None] = print) -> int:
    try:
        parsed = _parse_value(key, value)
        if key.startswith("terminal."):
            profile = save_terminal_preference(key.removeprefix("terminal."), value)
            output(f"Saved {key} in {user_config_path()} (active theme: {profile.theme}).")
            return 0
        config = load_user_config()
        if key == "banner":
            config[key] = parsed
        else:
            section_name, field_name = key.split(".", maxsplit=1)
            section = config.setdefault(section_name, {})
            if not isinstance(section, dict):
                section = {}
                config[section_name] = section
            section[field_name] = parsed
        path = save_user_config(config)
    except (ValueError, UserConfigError) as exc:
        output(str(exc))
        return 2
    output(f"Saved {key} in {path}.")
    return 0
