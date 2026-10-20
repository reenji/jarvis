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
    "bash.exe", "wsl.exe", "terminal", "iterm2", "visual studio code", "code.exe",
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
    return str(process_name or "").casefold().strip() in _BLOCKED_PROCESSES


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
