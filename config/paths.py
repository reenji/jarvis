"""Per-user Argus storage paths shared by configuration and state services."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def default_argus_data_dir() -> Path:
    override = os.environ.get("ARGUS_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Argus"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Argus"
    return Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state") / "argus"
