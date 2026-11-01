"""Environment-backed limits for screen interaction."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _number(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        return min(max(float(os.environ.get(name, default)), minimum), maximum)
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ScreenConfig:
    vision_model: str = "gemini-3.8-flash"
    max_image_side: int = 1568
    max_steps: int = 12
    max_seconds: float = 60.0
    settle_delay: float = 0.6
    focus_delay: float = 0.75
    mouse_move_duration: float = 0.2
    debug_screenshots: bool = False
    dry_run: bool = False
    kill_switch_hotkey: str = "ctrl+alt+shift+esc"

    @classmethod
    def from_env(cls) -> "ScreenConfig":
        return cls(
            vision_model=os.environ.get("ARGUS_VISION_MODEL", os.environ.get("VISION_MODEL", cls.vision_model)).strip() or cls.vision_model,
            max_image_side=int(_number("ARGUS_MAX_IMAGE_SIDE", cls.max_image_side, 640, 4096)),
            max_steps=int(_number("ARGUS_SCREEN_MAX_STEPS", cls.max_steps, 1, 30)),
            max_seconds=_number("ARGUS_SCREEN_MAX_SECONDS", cls.max_seconds, 5, 180),
            settle_delay=_number("ARGUS_SCREEN_SETTLE_DELAY", cls.settle_delay, 0.1, 5),
            focus_delay=_number("ARGUS_SCREEN_FOCUS_DELAY", cls.focus_delay, 0, 10),
            mouse_move_duration=_number("ARGUS_SCREEN_MOUSE_DURATION", cls.mouse_move_duration, 0, 1),
            debug_screenshots=os.environ.get("ARGUS_DEBUG_SCREENSHOTS", "false").strip().lower() in {"1", "true", "yes", "on"},
            dry_run=os.environ.get("ARGUS_SCREEN_DRY_RUN", "false").strip().lower() in {"1", "true", "yes", "on"},
            kill_switch_hotkey=os.environ.get("ARGUS_SCREEN_KILL_SWITCH", cls.kill_switch_hotkey).strip() or cls.kill_switch_hotkey,
        )
