"""Client contracts for the transport-neutral ARGUS live engine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


class VoiceSelector(Protocol):
    """Small legacy surface used to read a desktop voice selector."""

    def currentIndex(self) -> int: ...

    def itemData(self, index: int) -> Any: ...

    def currentText(self) -> str: ...


@runtime_checkable
class ArgusClient(Protocol):
    """Transport-neutral events required by the live conversation engine.

    Desktop, terminal, and hosted adapters implement these conversation events.
    Adapter-specific controls such as themes and window commands are optional
    capabilities and deliberately do not belong to this base contract.
    """

    on_text_command: Callable[[str], None] | None

    def write_log(self, text: str) -> None: ...

    def set_state(self, state: str) -> None: ...

    def show_subtitle(self, text: str) -> None: ...

    def clear_subtitle(self) -> None: ...


@runtime_checkable
class ArgusDesktopClient(ArgusClient, Protocol):
    """Optional desktop controls consumed only when an adapter provides them."""

    @property
    def muted(self) -> bool: ...

    @property
    def current_file(self) -> str | None: ...

    @property
    def _voice_combo(self) -> VoiceSelector | None: ...

    def set_theme(self, theme_key: str) -> None: ...

    def set_graphics_quality(self, quality: str) -> None: ...

    def sync_voice_display(self, voice_name: str) -> None: ...

    def handle_ui_command(self, action: str) -> None: ...
