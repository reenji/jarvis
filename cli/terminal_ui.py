"""Rich terminal presentation with a plain-text fallback."""

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any


class TerminalUI:
    def __init__(
        self,
        *,
        console: Any | None = None,
        error_console: Any | None = None,
        output: Callable[[str], None] | None = None,
        error_output: Callable[[str], None] | None = None,
    ) -> None:
        self._output = output or print
        self._error_output = error_output or (lambda text: print(text, file=sys.stderr))
        self.console = console
        self.error_console = error_console
        if console is None and output is None and error_output is None:
            try:
                from rich.console import Console

                self.console = Console(highlight=False, soft_wrap=True)
                self.error_console = error_console or Console(
                    stderr=True,
                    highlight=False,
                    soft_wrap=True,
                )
            except ImportError:
                self.console = None
                self.error_console = None

    def banner(self) -> None:
        if self.console is None:
            self._output("  (o) ARGUS — seu assistente no terminal")
            return

        from rich.panel import Panel
        from rich.text import Text

        title = Text("◉  ARGUS", style="bold bright_cyan", justify="center")
        title.append("\nSeu assistente no terminal", style="dim")
        self.console.print(Panel.fit(title, border_style="cyan", padding=(0, 2)))

    def info(self, text: str) -> None:
        if self.console is None:
            self._output(text)
            return
        from rich.text import Text

        self.console.print(Text(text, style="dim cyan"))

    def system(self, text: str) -> None:
        value = str(text)
        already_prefixed = value.startswith("[ARGUS] ")
        if self.console is None:
            self._output(value if already_prefixed else f"[ARGUS] {value}")
            return
        from rich.text import Text

        line = Text("" if already_prefixed else "[ARGUS] ", style="bold cyan")
        if already_prefixed:
            line.append("[ARGUS] ", style="bold cyan")
            value = value[len("[ARGUS] "):]
        line.append(value, style="dim")
        self.console.print(line)

    def error(self, text: str) -> None:
        if self.console is None:
            self._error_output(text)
            return
        from rich.text import Text

        target = self.error_console or self.console
        target.print(Text(str(text), style="bold red"))

    def assistant(self, text: str) -> None:
        if self.console is None:
            self._output(f"ARGUS> {text}")
            return

        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.text import Text

        self.console.print(
            Panel(
                Markdown(str(text)),
                title=Text("ARGUS", style="bold bright_cyan"),
                border_style="cyan",
                padding=(0, 1),
            )
        )
