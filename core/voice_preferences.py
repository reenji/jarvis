"""Persist user-facing speech and listening preferences."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_VAD_SILENCE_MS = 700
MIN_VAD_SILENCE_MS = 500
MAX_VAD_SILENCE_MS = 1200
RESPONSE_STYLES = {"concise", "balanced", "detailed"}
DEFAULT_RESPONSE_STYLE = "balanced"
UI_SETTINGS_PATH = Path.home() / ".argus" / "config" / "settings.json"


def _settings_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else UI_SETTINGS_PATH


def normalize_silence_ms(value: object) -> int:
    try:
        silence_ms = int(value)
    except (TypeError, ValueError, OverflowError):
        silence_ms = DEFAULT_VAD_SILENCE_MS
    return max(MIN_VAD_SILENCE_MS, min(MAX_VAD_SILENCE_MS, silence_ms))


def normalize_response_style(value: object) -> str:
    style = str(value or DEFAULT_RESPONSE_STYLE).strip().lower()
    return style if style in RESPONSE_STYLES else DEFAULT_RESPONSE_STYLE


def load_voice_preferences(path: str | Path | None = None) -> dict[str, object]:
    try:
        data = json.loads(_settings_path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        data = {}
    return {
        "vad_silence_ms": normalize_silence_ms(data.get("vad_silence_ms")),
        "response_style": normalize_response_style(data.get("voice_response_style")),
    }


def save_voice_preferences(
    *,
    path: str | Path | None = None,
    vad_silence_ms: object | None = None,
    response_style: object | None = None,
) -> dict[str, object]:
    target = _settings_path(path)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        data = {}

    if vad_silence_ms is not None:
        data["vad_silence_ms"] = normalize_silence_ms(vad_silence_ms)
    if response_style is not None:
        data["voice_response_style"] = normalize_response_style(response_style)

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return load_voice_preferences(target)
