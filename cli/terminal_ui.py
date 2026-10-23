"""Rich terminal presentation with a plain-text fallback."""

from __future__ import annotations

import sys
from contextlib import contextmanager
from collections.abc import Callable
from typing import Any

from cli.banner import EYE_BANNER, banner_details


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
        package_version, model = banner_details()
        details = f"ARGUS CLI v{package_version} | model: {model}"

        if self.console is None:
            self._output(EYE_BANNER)
            self._output(details)
            return

        from rich.text import Text

        self.console.print(Text(EYE_BANNER, style="bold bright_cyan"))
        self.console.print(Text(details, style="bold cyan"))

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

    @contextmanager
    def response_stream(self):
        """Show a temporary live Markdown preview while Gemini is responding."""
        if self.console is None or not self.console.is_terminal:
            yield lambda _chunk: None
            return

        from rich.live import Live
        from rich.markdown import Markdown

        buffer = []
        with Live(
            Markdown(""),
            console=self.console,
            transient=True,
            refresh_per_second=12,
        ) as live:
            def update(chunk: str) -> None:
                buffer.append(str(chunk))
                live.update(Markdown("".join(buffer)), refresh=True)

            yield update
