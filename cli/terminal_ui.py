"""Rich terminal presentation with a plain-text fallback."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from collections.abc import Callable
from typing import Any

from cli.banner import EYE_BANNER, banner_details

ACCENT = "#e1b753"
ACCENT_DIM = "#806c3e"
SUCCESS = "#8ebd82"


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

                self.console = Console(
                    highlight=False,
                    soft_wrap=True,
                    no_color="NO_COLOR" in os.environ,
                )
                self.error_console = error_console or Console(
                    stderr=True,
                    highlight=False,
                    soft_wrap=True,
                    no_color="NO_COLOR" in os.environ,
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

        line = Text("● ARGUS", style=f"bold {ACCENT}")
        line.append(f"  {details.removeprefix('ARGUS CLI ')}", style="dim")
        self.console.print(line)
        self.console.rule(style=ACCENT_DIM)

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

        finished = value.startswith("Finished ")
        line = Text("  ✓ " if finished else "  ◌ ", style=SUCCESS if finished else ACCENT)
        if already_prefixed:
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
                title=Text("ARGUS", style=f"bold {ACCENT}"),
                border_style=ACCENT,
                padding=(0, 1),
            )
        )

    def user_turn(self, text: str) -> None:
        value = str(text or "").strip()
        if self.console is None:
            self._output(f"● {value}")
            return

        from rich.panel import Panel
        from rich.text import Text

        self.console.print(
            Panel(
                Text(value, style="bold white"),
                title=Text("● REQUEST", style=f"bold {ACCENT}"),
                border_style=ACCENT_DIM,
                padding=(0, 1),
            )
        )

    def turn_status(
        self,
        model: str,
        usage: dict[str, int],
        duration_seconds: float,
    ) -> None:
        """Show compact model, token, and duration details after a response."""
        details = [str(model or "ARGUS")]
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        total_tokens = usage.get("total_tokens")
        if input_tokens is not None or output_tokens is not None:
            counts = []
            if input_tokens is not None:
                counts.append(f"{input_tokens:,} in")
            if output_tokens is not None:
                counts.append(f"{output_tokens:,} out")
            token_detail = " / ".join(counts) + " tokens"
            if total_tokens is not None:
                token_detail += f" ({total_tokens:,} total)"
            details.append(token_detail)
        details.append(f"{max(0.0, float(duration_seconds)):.1f}s")
        value = "  $ " + "  |  ".join(details)

        if self.console is None:
            self._output(value)
            return

        from rich.text import Text

        self.console.print(Text(value, style=f"{ACCENT} dim"))

    @contextmanager
    def response_stream(self):
        """Show a temporary live Markdown preview while Gemini is responding."""
        if self.console is None or not self.console.is_terminal:
            yield lambda _chunk: None
            return

        from rich.live import Live
        from rich.markdown import Markdown
        from rich.panel import Panel

        buffer = []
        with Live(
            Panel(Markdown("Respondendo…"), title="ARGUS", border_style=ACCENT),
            console=self.console,
            transient=True,
            refresh_per_second=12,
        ) as live:
            def update(chunk: str) -> None:
                buffer.append(str(chunk))
                live.update(
                    Panel(
                        Markdown("".join(buffer)),
                        title="ARGUS",
                        border_style=ACCENT,
                    ),
                    refresh=True,
                )

            yield update
