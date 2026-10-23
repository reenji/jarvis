"""Interruption and sensitive-file checks for screen-control runs."""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path


_SENSITIVE_NAMES = re.compile(
    r"(^|[._-])(?:\.env(?:\..*)?|dockerfile|docker-compose(?:\..*)?|"
    r"credentials?(?:\..*)?|secrets?(?:\..*)?|id_rsa|id_ed25519|"
    r"private[-_ ]?key|service[-_ ]account)(?:$|[._-])",
    re.IGNORECASE,
)
_SECRET_CONTENT = re.compile(
    r"(?im)^\s*(?:[A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|CLIENT_SECRET)"
    r"|AWS_SECRET_ACCESS_KEY|DATABASE_URL)\s*[:=]\s*\S+"
)
_BLOCKED_PROCESSES = {
    "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "wt.exe",
    "conhost.exe", "openconsole.exe", "bash.exe", "wsl.exe", "terminal",
    "terminal.app", "iterm2", "gnome-terminal", "gnome-terminal-server",
    "konsole", "xterm", "urxvt", "alacritty", "kitty", "tilix",
    "wezterm", "wezterm-gui", "foot", "contour", "rio", "tabby", "hyper",
    "visual studio code", "code.exe",
}
_BLOCKED_TARGETS = {
    "cmd", "command prompt", "powershell", "windows powershell", "pwsh",
    "windows terminal", "terminal", "console", "bash", "zsh", "fish",
    "wsl", "iterm", "iterm2", "gnome terminal", "konsole", "xterm",
    "alacritty", "kitty", "tilix", "wezterm", "foot", "visual studio code",
    "vscode", "code",
}


def sensitive_file_reason(path_or_name: str) -> str | None:
    """Return a safe reason string without exposing any secret value."""
    raw = str(path_or_name or "").strip().strip('"')
    if not raw:
        return None
    path = Path(raw)
    name = path.name or raw
    lowered = name.casefold()
    if lowered == ".env" or lowered.startswith(".env."):
        return "arquivo de configuração de ambiente"
    if _SENSITIVE_NAMES.search(name):
        return "nome de arquivo de credenciais, segredos ou configuração operacional"
    try:
        if path.is_file() and path.stat().st_size <= 2_000_000:
            sample = path.read_text(encoding="utf-8", errors="ignore")[:64_000]
            if _SECRET_CONTENT.search(sample):
                return "conteúdo com possível credencial ou segredo"
    except (OSError, ValueError):
        pass
    return None


def is_blocked_process(process_name: str) -> bool:
    process = str(process_name or "").casefold().strip()
    return process in _BLOCKED_PROCESSES or process.removesuffix(".exe") in _BLOCKED_PROCESSES


def is_blocked_terminal_window(title: str, process_name: str = "") -> bool:
    if is_blocked_process(process_name):
        return True
    normalized = " ".join(str(title or "").casefold().split())
    return any(marker in normalized for marker in (
        "windows terminal", "command prompt", "powershell", "cmd.exe",
        "terminal.app", "iterm2", "gnome-terminal", "konsole",
    )) or normalized.startswith(("terminal", "bash -", "zsh -", "fish -"))


def is_blocked_terminal_target(value: str) -> bool:
    target = " ".join(str(value or "").casefold().replace(".exe", "").split())
    return target in _BLOCKED_TARGETS


class AbortController:
    """Event-based kill switch; a global hotkey is used when `keyboard` exists."""

    def __init__(self, hotkey: str = "ctrl+alt+shift+esc"):
        self._event = threading.Event()
        self._hotkey = hotkey.strip().lower()
        self._listener = None

    @property
    def aborted(self) -> bool:
        return self._event.is_set()

    def abort(self) -> None:
        self._event.set()

    def start(self) -> None:
        try:
            import keyboard
            self._listener = keyboard.add_hotkey(self._hotkey, self.abort, suppress=False)
        except Exception:
            self._listener = None

    def stop(self) -> None:
        if self._listener is not None:
            try:
                import keyboard
                keyboard.remove_hotkey(self._listener)
            except Exception:
                pass
            self._listener = None
