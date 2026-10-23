"""Optional Gemini Live voice mode for the terminal client."""

from __future__ import annotations

import asyncio
import importlib.util
from collections.abc import Callable
from typing import Any

from cli.client import TerminalClient

VOICE_UNAVAILABLE = 3


def _audio_unavailable_reason(
    *,
    audio_available: Callable[[], bool] | None = None,
    devices_loader: Callable[[], Any] | None = None,
) -> str | None:
    """Check optional audio support without opening a microphone or speaker."""
    if audio_available is None:
        try:
            audio_available = lambda: importlib.util.find_spec("sounddevice") is not None
        except (ImportError, ValueError):
            audio_available = lambda: False
    try:
        if not audio_available():
            return "Voice support is not installed; reinstall ARGUS with its optional [voice] extra."
    except Exception:
        return "Voice support could not load its optional audio dependency."

    try:
        if devices_loader is None:
            import sounddevice as sd

            devices_loader = sd.query_devices
        devices = devices_loader()
    except Exception as exc:
        return f"Voice audio devices are unavailable ({type(exc).__name__}); check device access and OS permissions."

    try:
        device_list = list(devices.values() if isinstance(devices, dict) else devices)
        has_input = any(int(device.get("max_input_channels", 0)) > 0 for device in device_list)
        has_output = any(int(device.get("max_output_channels", 0)) > 0 for device in device_list)
    except (AttributeError, TypeError, ValueError):
        return "Voice audio devices could not be inspected."
    if not has_input or not has_output:
        missing = "microphone" if not has_input else "speaker"
        if not has_input and not has_output:
            missing = "microphone and speaker"
        return f"No usable {missing} is available; check device connections and OS permissions."
    return None


class VoiceTerminalClient(TerminalClient):
    """Render complete voice transcripts without a desktop subtitle widget."""

    def write_log(self, text: str) -> None:
        value = str(text or "")
        if value.startswith("You: "):
            self._output(f"Você> {value[5:]}")
        elif value.startswith("Argus: "):
            self._output(f"ARGUS> {value[7:]}")
        else:
            super().write_log(value)

    def show_subtitle(self, text: str) -> None:
        # The Live engine emits partial transcription chunks here. Printing the
        # final turn from write_log avoids choppy duplicate lines in a terminal.
        return None


def run_voice(
    *,
    output: Callable[[str], None] = print,
    live_factory: Callable[..., Any] | None = None,
    settings_loader: Callable[[], Any] | None = None,
    api_key_loader: Callable[[], str] | None = None,
    audio_available: Callable[[], bool] | None = None,
    audio_devices_loader: Callable[[], Any] | None = None,
    async_runner: Callable[[Any], Any] = asyncio.run,
) -> int:
    """Run the existing Gemini Live engine without starting the desktop UI."""
    if live_factory is None:
        unavailable = _audio_unavailable_reason(
            audio_available=audio_available,
            devices_loader=audio_devices_loader,
        )
        if unavailable:
            output(unavailable)
            return VOICE_UNAVAILABLE
        try:
            from main import ArgusLive
        except ImportError as exc:
            output(
                "Voice mode could not load its optional desktop dependencies "
                f"({getattr(exc, 'name', None) or type(exc).__name__}); check the installed voice extra."
            )
            return VOICE_UNAVAILABLE
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

    terminal = VoiceTerminalClient(output=output)
    try:
        assistant = live_factory(
            terminal,
            str(getattr(settings.voice, "name", "puck") or "puck"),
            api_key=api_key,
        )
    except Exception as exc:
        output(f"Could not initialize voice mode ({type(exc).__name__}).")
        return 2
    output("ARGUS voice is listening. Speak naturally; press Ctrl+C to exit.")
    try:
        async_runner(assistant.run())
    except KeyboardInterrupt:
        assistant.request_shutdown()
        output("ARGUS voice session ended.")
        return 130
    except Exception as exc:
        output(f"Voice session failed ({type(exc).__name__}). Check Gemini and audio device access.")
        return 1
    return 0
