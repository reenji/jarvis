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

    def wait_for_manual_browser_resolution(self) -> bool:
        message = (
            "A verificação anti-robô precisa ser concluída manualmente no navegador. "
            "Depois pressione Enter para retomar uma vez; Ctrl+C cancela."
        )
        self._output(message)
        if not sys.stdin.isatty():
            self._output("Este terminal não aceita entrada interativa; resolva o desafio e repita o pedido.")
            return False
        try:
            from prompt_toolkit import prompt as prompt_toolkit_prompt
        except ImportError:
            prompt_toolkit_prompt = input
        try:
            prompt_toolkit_prompt("Resolvido? Pressione Enter para continuar: ")
        except (EOFError, KeyboardInterrupt):
            return False
        return True

    def confirm_sensitive_file(self, name: str, reason: str) -> bool:
        self._output(
            f"O arquivo {name!r} parece ser {reason}. "
            "Vou compartilhá-lo com o destino pedido. Confirmar? [s/N]"
        )
        if not sys.stdin.isatty():
            self._output("Sem confirmação interativa, não compartilhei o arquivo.")
            return False
        try:
            from prompt_toolkit import prompt as prompt_toolkit_prompt
        except ImportError:
            prompt_toolkit_prompt = input
        try:
            answer = prompt_toolkit_prompt("Confirma o compartilhamento? [s/N] ").strip().casefold()
        except (EOFError, KeyboardInterrupt):
            return False
        return answer in {"s", "sim", "y", "yes"}

    def start_speaking(self) -> None:
        self.set_state("SPEAKING")

    def stop_speaking(self) -> None:
        self.set_state("IDLE")
