"""User preference for per-action mouse and keyboard confirmations."""

from __future__ import annotations

import json
from pathlib import Path


UI_SETTINGS_PATH = Path.home() / ".argus" / "config" / "settings.json"
SETTING_KEY = "direct_computer_control_enabled"


def _read_settings(path: str | Path | None = None) -> tuple[Path, dict]:
    target = Path(path) if path is not None else UI_SETTINGS_PATH
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        data = {}
    return target, data


def load_direct_computer_control(path: str | Path | None = None) -> bool:
    _, data = _read_settings(path)
    # Direct completion is the default; users can turn it off in Settings.
    value = data.get(SETTING_KEY, True)
    return value if isinstance(value, bool) else True


def save_direct_computer_control(enabled: bool, path: str | Path | None = None) -> bool:
    target, data = _read_settings(path)
    data[SETTING_KEY] = bool(enabled)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return bool(data[SETTING_KEY])
