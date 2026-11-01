"""Per-user appearance and identity settings for the ARGUS terminal UI."""

from __future__ import annotations

import getpass
import os
import unicodedata
from dataclasses import dataclass
from typing import Any

from config.user_config import load_user_config, save_user_config


@dataclass(frozen=True)
class TerminalTheme:
    name: str
    primary: str
    secondary: str
    muted: str
    success: str
    user: str


THEMES: dict[str, TerminalTheme] = {
    "cyan": TerminalTheme("cyan", "#4dd0e1", "#75b9c7", "#688087", "#8ebd82", "#f2f5f7"),
    "amber": TerminalTheme("amber", "#e1b753", "#b99a54", "#80775f", "#8ebd82", "#f2f5f7"),
    "matrix": TerminalTheme("matrix", "#72e58b", "#55b96b", "#68806c", "#a1e9a7", "#e7f4e9"),
    "mono": TerminalTheme("mono", "#e4e4e4", "#b4b4b4", "#777777", "#c7c7c7", "#ffffff"),
}

DEFAULT_ASSISTANT_NAME = "ARGUS"
MAX_DISPLAY_NAME_LENGTH = 32


def _clean_display_name(value: object, *, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    cleaned = "".join(
        character
        for character in value.strip()
        if unicodedata.category(character) not in {"Cc", "Cf", "Cs"}
    )
    cleaned = " ".join(cleaned.split())[:MAX_DISPLAY_NAME_LENGTH]
    return cleaned or fallback


def _system_user_name() -> str:
    try:
        value = os.environ.get("USERNAME") or os.environ.get("USER") or getpass.getuser()
    except Exception:
        value = "you"
    return _clean_display_name(value, fallback="you")


@dataclass(frozen=True)
class TerminalProfile:
    assistant_name: str = DEFAULT_ASSISTANT_NAME
    user_name: str = ""
    theme: str = "cyan"

    @property
    def colors(self) -> TerminalTheme:
        return THEMES[self.theme]


def load_terminal_profile(config: dict[str, Any] | None = None) -> TerminalProfile:
    """Read profile values from this OS user's Argus configuration."""
    try:
        current = config if config is not None else load_user_config()
    except Exception:
        current = {}
    raw = current.get("terminal", {}) if isinstance(current, dict) else {}
    if not isinstance(raw, dict):
        raw = {}

    theme_value = raw.get("theme", "cyan")
    theme = str(theme_value).strip().casefold() if isinstance(theme_value, str) else "cyan"
    if theme not in THEMES:
        theme = "cyan"

    return TerminalProfile(
        assistant_name=_clean_display_name(
            raw.get("assistant_name"), fallback=DEFAULT_ASSISTANT_NAME
        ),
        user_name=_clean_display_name(raw.get("user_name"), fallback=_system_user_name()),
        theme=theme,
    )


def save_terminal_preference(key: str, value: str) -> TerminalProfile:
    """Validate and persist one user-scoped terminal preference."""
    allowed_keys = {"theme", "assistant_name", "user_name"}
    if key not in allowed_keys:
        raise ValueError("Supported terminal preferences: theme, assistant_name, user_name.")

    config = load_user_config()
    terminal = config.get("terminal")
    if not isinstance(terminal, dict):
        terminal = {}
        config["terminal"] = terminal

    if key == "theme":
        normalized = value.strip().casefold()
        if normalized not in THEMES:
            choices = ", ".join(THEMES)
            raise ValueError(f"Unknown terminal theme. Choose one of: {choices}.")
        terminal[key] = normalized
    else:
        cleaned = _clean_display_name(value, fallback="")
        if not cleaned:
            raise ValueError(f"{key} must contain a visible name.")
        terminal[key] = cleaned

    save_user_config(config)
    return load_terminal_profile(config)
