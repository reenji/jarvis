"""Private local storage for resumable text sessions."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class SessionSummary:
    id: str
    title: str
    created_at: str
    updated_at: str


def default_database_path() -> Path:
    """Resolve the platform's user state directory without touching the repo."""
    override = os.environ.get("ARGUS_SESSION_DB")
    if override:
        return Path(override).expanduser()

    argus_home = os.environ.get("ARGUS_HOME")
    if argus_home:
        root = Path(argus_home).expanduser()
    elif sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Argus"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "Argus"
    else:
        root = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "argus"
    return root / "sessions.sqlite3"


class SessionStore:
    """SQLite-backed CLI history, separate from ARGUS long-term memory."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        retention_days: int | None = None,
    ) -> None:
        self.path = Path(path) if path is not None else default_database_path()
        if retention_days is None:
            try:
                retention_days = int(os.environ.get("ARGUS_SESSION_RETENTION_DAYS", "30"))
            except ValueError:
                retention_days = 30
        self.retention_days = max(0, retention_days)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._secure_permissions(self.path.parent, directory=True)
        self._initialize()
        self._delete_expired()

    @staticmethod
    def _secure_permissions(path: Path, *, directory: bool = False) -> None:
        try:
            os.chmod(path, 0o700 if directory else 0o600)
        except OSError:
            # Windows permissions come from the containing user's profile ACL.
            pass

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    history_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS sessions_updated_at ON sessions(updated_at DESC)"
            )
        self._secure_permissions(self.path)

    def _delete_expired(self) -> None:
        if not self.retention_days:
            return
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.retention_days)).isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE updated_at < ?", (cutoff,))

    def create(self, title: str = "New conversation") -> str:
        session_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        cleaned_title = " ".join(str(title or "New conversation").split())[:120]
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions(id, title, history_json, created_at, updated_at) VALUES (?, ?, '[]', ?, ?)",
                (session_id, cleaned_title or "New conversation", now, now),
            )
        self._secure_permissions(self.path)
        return session_id

    def list(self, limit: int = 20) -> list[SessionSummary]:
        safe_limit = min(max(int(limit), 1), 100)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [SessionSummary(**dict(row)) for row in rows]

    def resolve(self, session_id: str) -> str | None:
        candidate = str(session_id or "").strip()
        if not candidate:
            return None
        with self._connect() as connection:
            row = connection.execute("SELECT id FROM sessions WHERE id = ?", (candidate,)).fetchone()
            if row:
                return str(row["id"])
            matches = connection.execute(
                "SELECT id FROM sessions WHERE id LIKE ? ORDER BY updated_at DESC LIMIT 2",
                (candidate + "%",),
            ).fetchall()
        if len(matches) == 1:
            return str(matches[0]["id"])
        return None

    def load_history(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT history_json FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"Session not found: {session_id}")
        try:
            history = json.loads(row["history_json"])
        except (TypeError, json.JSONDecodeError):
            history = []
        return history if isinstance(history, list) else []

    def save_history(self, session_id: str, history: list[dict[str, Any]]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(history, ensure_ascii=False, separators=(",", ":"))
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE sessions SET history_json = ?, updated_at = ? WHERE id = ?",
                (payload, now, session_id),
            )
            if result.rowcount != 1:
                raise KeyError(f"Session not found: {session_id}")
        self._secure_permissions(self.path)

    def clear(self, session_id: str) -> None:
        self.save_history(session_id, [])

    def delete(self, session_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return result.rowcount == 1
