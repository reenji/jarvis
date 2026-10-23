"""Optional Gemini Live voice mode for the terminal client."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from cli.client import TerminalClient


def run_voice(
    *,
    output: Callable[[str], None] = print,
    live_factory: Callable[..., Any] | None = None,
    settings_loader: Callable[[], Any] | None = None,
    api_key_loader: Callable[[], str] | None = None,
    async_runner: Callable[[Any], Any] = asyncio.run,
) -> int:
    """Run the existing Gemini Live engine without starting the desktop UI."""
    if live_factory is None:
        try:
            from main import ArgusLive
        except ImportError as exc:
            output(
                "Voice mode needs the optional desktop audio dependencies. "
                "Install the project's desktop requirements, then run `argus voice` again."
            )
            return 2
        live_factory = ArgusLive

    try:
        if settings_loader is None or api_key_loader is None:
            from config.settings import get_api_key, get_settings

            settings_loader = settings_loader or get_settings
            api_key_loader = api_key_loader or get_api_key
        settings = settings_loader()
        api_key = api_key_loader()
    except (ImportError, ValueError, OSError) as exc:
        output(f"Voice mode is not configured: {exc}")
        output("Run `argus setup` to configure and validate Gemini access.")
        return 2

    terminal = TerminalClient(output=output)
    assistant = live_factory(
        terminal,
        str(getattr(settings.voice, "name", "puck") or "puck"),
        api_key=api_key,
    )
    output("ARGUS voice is listening. Speak naturally; press Ctrl+C to exit.")
    try:
        async_runner(assistant.run())
    except KeyboardInterrupt:
        assistant.request_shutdown()
        output("ARGUS voice session ended.")
        return 130
    except Exception as exc:
        output(f"Voice session failed ({type(exc).__name__}): {str(exc)[:240]}")
        return 1
    return 0
