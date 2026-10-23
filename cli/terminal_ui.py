"""Rich terminal presentation with a plain-text fallback."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from collections.abc import Callable
from pathlib import Path
from typing import Any

from cli.banner import EYE_BANNER, banner_details
from cli.terminal_profile import TerminalProfile, load_terminal_profile

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
        profile: TerminalProfile | None = None,
    ) -> None:
        self._output = output or print
        self._error_output = error_output or (lambda text: print(text, file=sys.stderr))
        self.profile = profile or load_terminal_profile()
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

        line = Text(f"● {self.profile.assistant_name}", style=f"bold {self.profile.colors.primary}")
        line.append(f"  {details.removeprefix('ARGUS CLI ')}", style="dim")
        self.console.print(line)
        self.console.rule(style=self.profile.colors.secondary)

    def dashboard(
        self,
        *,
        package_version: str,
        model: str,
        session_id: str,
        workspace: str | Path,
        tool_declarations: list[dict[str, Any]] | None = None,
        api_ready: bool | None = None,
    ) -> None:
        """Render the interactive startup dashboard in the current user's style."""
        declarations = tool_declarations or []
        groups = _group_tool_names(declarations)
        workspace_name = Path(workspace).name or str(workspace)
        workspace_name = _truncate(workspace_name, 34)
        tool_count = len(declarations)
        profile = self.profile

        if self.console is None:
            self._output(f"{profile.assistant_name} CLI v{package_version}")
            self._output(f"User: {profile.user_name} | Theme: {profile.theme} | Model: {model}")
            self._output(f"Session: {session_id[:12]} | Workspace: {workspace_name}")
            if api_ready is not None:
                api_status = "key configured" if api_ready else "key missing — run `argus setup`"
                self._output(f"Gemini: {api_status}")
            self._output(f"Available actions ({tool_count}):")
            for category, names in groups.items():
                self._output(f"  {category}: {', '.join(names)}")
            self._output("Commands: /help  /status  /tools  /theme  /profile  /exit")
            self._output("=" * 64)
            return

        from rich import box
        from rich.columns import Columns
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        colors = profile.colors
        logo = Text(
            " ███   ████    ████  █   █   ████\n"
            "█   █  █   █  █      █   █  █    \n"
            "█████  ████   █ ███  █   █   ███ \n"
            "█   █  █  █   █   █  █   █      █\n"
            "█   █  █   █   ████   ███   ████ ",
            style=f"bold {colors.primary}",
        )
        title = Table.grid(expand=True)
        title.add_column(ratio=1)
        title.add_column(justify="right")
        title.add_row(
            logo,
            Text(f"ARGUS CLI v{package_version}", style=f"bold {colors.secondary}"),
        )
        self.console.print(title)

        status = Table.grid(padding=(0, 1))
        status.add_column(style=f"{colors.primary} bold", no_wrap=True)
        status.add_column(style="white")
        status.add_row("agent", profile.assistant_name)
        status.add_row("user", profile.user_name)
        status.add_row("model", _truncate(model, 38))
        status.add_row("session", session_id[:12])
        status.add_row("workspace", workspace_name)
        if api_ready is not None:
            status.add_row(
                "Gemini",
                Text("key configured" if api_ready else "key missing · run argus setup",
                     style=colors.success if api_ready else "bold yellow"),
            )
        status_panel = Panel(
            status,
            title=Text(" YOUR SESSION ", style=f"bold {colors.primary}"),
            border_style=colors.secondary,
            box=box.DOUBLE,
            padding=(0, 1),
        )

        actions = Table.grid(padding=(0, 1))
        actions.add_column(style=f"{colors.primary} bold", no_wrap=True)
        actions.add_column(style="white")
        if groups:
            for category, names in groups.items():
                actions.add_row(category, ", ".join(names))
        else:
            actions.add_row("status", "Action inventory unavailable")
        action_panel = Panel(
            actions,
            title=Text(f" AVAILABLE ACTIONS · {tool_count} ", style=f"bold {colors.primary}"),
            border_style=colors.secondary,
            box=box.DOUBLE,
            padding=(0, 1),
        )

        width = getattr(getattr(self.console, "size", None), "width", 100)
        panels = [status_panel, action_panel]
        self.console.print(Columns(panels, equal=True, expand=True) if width >= 94 else panels[0])
        if width < 94:
            self.console.print(action_panel)

        shortcuts = Text()
        shortcuts.append("/help", style=f"bold {colors.primary}")
        shortcuts.append(" help   ")
        shortcuts.append("/tools", style=f"bold {colors.primary}")
        shortcuts.append(" actions   ")
        shortcuts.append("/theme", style=f"bold {colors.primary}")
        shortcuts.append(" personalize   ")
        shortcuts.append("/exit", style=f"bold {colors.primary}")
        shortcuts.append(" save & exit")
        self.console.print(Panel(shortcuts, border_style=colors.muted, box=box.SQUARE, padding=(0, 1)))

    def show_status(self, *, model: str, session_id: str, tool_count: int, api_ready: bool) -> None:
        """Show a compact live status block, matching the startup dashboard."""
        self.info(
            f"{self.profile.assistant_name} · {self.profile.user_name} · theme {self.profile.theme}\n"
            f"model {model} · session {session_id[:12]} · {tool_count} actions · "
            f"Gemini {'key configured' if api_ready else 'needs setup'}"
        )

    def show_tools(self, tool_declarations: list[dict[str, Any]]) -> None:
        """List the full action inventory without loading descriptions or secrets."""
        names = sorted(
            str(declaration.get("name", "")).strip()
            for declaration in tool_declarations
            if declaration.get("name")
        )
        if self.console is None:
            self._output(f"Available actions ({len(names)}):")
            for name in names:
                self._output(f"  · {name}")
            return

        from rich import box
        from rich.panel import Panel
        from rich.text import Text

        content = Text("  · " + "\n  · ".join(names), style="white") if names else Text("No actions are enabled.")
        self.console.print(
            Panel(
                content,
                title=f"AVAILABLE ACTIONS · {len(names)}",
                border_style=self.profile.colors.secondary,
                box=box.DOUBLE,
                padding=(0, 1),
            )
        )

    def info(self, text: str) -> None:
        if self.console is None:
            self._output(text)
            return
        from rich.text import Text

        self.console.print(Text(text, style=f"dim {self.profile.colors.secondary}"))

    def system(self, text: str) -> None:
        value = str(text)
        already_prefixed = value.startswith("[ARGUS] ")
        if self.console is None:
            self._output(value if already_prefixed else f"[ARGUS] {value}")
            return
        from rich.text import Text

        finished = value.startswith("Finished ")
        line = Text(
            "  ✓ " if finished else "  ◌ ",
            style=self.profile.colors.success if finished else self.profile.colors.primary,
        )
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
            self._output(f"{self.profile.assistant_name}> {text}")
            return

        from rich.markdown import Markdown
        from rich.panel import Panel
        from rich.text import Text

        self.console.print(
            Panel(
                Markdown(str(text)),
                title=Text(self.profile.assistant_name, style=f"bold {self.profile.colors.primary}"),
                border_style=self.profile.colors.primary,
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
                title=Text(f"● {self.profile.user_name}", style=f"bold {self.profile.colors.primary}"),
                border_style=self.profile.colors.secondary,
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

        self.console.print(Text(value, style=f"{self.profile.colors.primary} dim"))

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
            Panel(
                Markdown("Respondendo…"),
                title=self.profile.assistant_name,
                border_style=self.profile.colors.primary,
            ),
            console=self.console,
            transient=True,
            refresh_per_second=12,
        ) as live:
            def update(chunk: str) -> None:
                buffer.append(str(chunk))
                live.update(
                    Panel(
                        Markdown("".join(buffer)),
                        title=self.profile.assistant_name,
                        border_style=self.profile.colors.primary,
                    ),
                    refresh=True,
                )

            yield update


def _truncate(value: object, limit: int) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _group_tool_names(declarations: list[dict[str, Any]]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "desktop": [],
        "web": [],
        "media": [],
        "files & work": [],
        "messaging": [],
        "other": [],
    }
    for declaration in declarations:
        name = str(declaration.get("name", "")).strip()
        if not name:
            continue
        lowered = name.casefold()
        if any(token in lowered for token in ("computer", "screen", "open_app", "desktop", "window")):
            category = "desktop"
        elif any(token in lowered for token in ("browser", "search", "web", "youtube")):
            category = "web"
        elif any(token in lowered for token in ("media", "music", "spotify")):
            category = "media"
        elif any(token in lowered for token in ("file", "document", "presentation", "spreadsheet", "knowledge")):
            category = "files & work"
        elif any(token in lowered for token in ("message", "discord", "email", "mail", "telegram", "whatsapp")):
            category = "messaging"
        else:
            category = "other"
        groups[category].append(name)

    visible: dict[str, list[str]] = {}
    for category, names in groups.items():
        if not names:
            continue
        shown = names[:4]
        if len(names) > len(shown):
            shown.append(f"+{len(names) - len(shown)} more")
        visible[category] = shown
    return visible
