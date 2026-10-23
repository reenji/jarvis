"""Terminal adapter for tool output and conversation status events."""

from __future__ import annotations

import sys
from collections.abc import Callable


class TerminalClient:
    def __init__(self, *, output: Callable[[str], None] | None = None) -> None:
        self.on_text_command = None
        self.muted = False
        self.current_file: str | None = None
        self.state = "IDLE"
        self._output = output or print

    def write_log(self, text: str) -> None:
        value = str(text or "")
        if value.startswith("SYS: "):
            self._output(f"[ARGUS] {value[5:]}")
        elif value.startswith("ERR: "):
            print(f"[ARGUS] {value[5:]}", file=sys.stderr)
        elif value.startswith(("You: ", "Argus: ")):
            return
        elif value:
            self._output(value)

    def set_state(self, state: str) -> None:
        self.state = str(state or "IDLE").upper()

    def show_subtitle(self, text: str) -> None:
        if text:
            self._output(str(text))

    def clear_subtitle(self) -> None:
        return None

    def start_speaking(self) -> None:
        self.set_state("SPEAKING")

    def stop_speaking(self) -> None:
        self.set_state("IDLE")
