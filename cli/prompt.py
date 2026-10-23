"""Interactive prompt history and slash-command completion."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from cli.history import default_database_path

SLASH_COMMANDS = (
    "/help",
    "/new",
    "/sessions",
    "/voice",
    "/doctor",
    "/resume",
    "/clear",
    "/delete",
    "/exit",
    "/quit",
)


def default_prompt_history_path() -> Path:
    return default_database_path().with_name("prompt-history")


def _secure_history_path(path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(path.parent, 0o700)
        if path.exists():
            os.chmod(path, 0o600)
    except OSError:
        # Windows relies on the user's profile ACL.
        pass


def create_slash_completer():
    from prompt_toolkit.completion import WordCompleter

    return WordCompleter(SLASH_COMMANDS, ignore_case=True, sentence=True)


class InteractivePrompt:
    """Reuse one prompt-toolkit session for arrow-key history and completion."""

    def __init__(
        self,
        *,
        history_path: str | Path | None = None,
        session_factory=None,
        interactive: bool | None = None,
    ) -> None:
        self.history_path = Path(history_path) if history_path else default_prompt_history_path()
        self._session_factory = session_factory
        self._interactive = interactive
        self._session: Any | None = None

    @staticmethod
    def _create_session(history_path: Path):
        from prompt_toolkit import PromptSession
        from prompt_toolkit.history import FileHistory, InMemoryHistory

        _secure_history_path(history_path)
        try:
            history = FileHistory(str(history_path))
        except OSError:
            history = InMemoryHistory()
        return PromptSession(
            history=history,
            completer=create_slash_completer(),
            complete_while_typing=True,
        )

    def prompt(self, message: str) -> str:
        interactive = self._interactive
        if interactive is None:
            interactive = bool(sys.stdin.isatty() and sys.stdout.isatty())
        if not interactive:
            return input(message)

        if self._session is None:
            factory = self._session_factory or self._create_session
            _secure_history_path(self.history_path)
            try:
                self._session = factory(self.history_path)
            except ImportError:
                return input(message)
        try:
            return str(self._session.prompt(message))
        finally:
            _secure_history_path(self.history_path)
