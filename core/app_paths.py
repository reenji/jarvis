"""Where ARGUS reads its bundled files and keeps the user's data.

From a source checkout both are the repository root. In a PyInstaller build:

- ``resource_dir()`` holds the files shipped inside the bundle
  (``sys._MEIPASS``): the live prompt, fonts and the app icon. Read only.
- ``data_dir()`` holds what the app writes: ``config/``, ``memory/``,
  ``outputs/`` and ``.env``. Windows keeps them beside ``ARGUS.exe``, since the
  installer is per user and 0.2.0 installs already store keys there. macOS
  (inside an ``.app``) and Linux (``/usr/lib/argus``) install read only, so
  their data goes to the user's application-data folder.

``ARGUS_DATA_DIR`` overrides the data folder of a build.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_SOURCE_ROOT = Path(__file__).resolve().parent.parent


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> Path:
    if _frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return _SOURCE_ROOT


def data_dir() -> Path:
    if not _frozen():
        return _SOURCE_ROOT
    override = os.environ.get("ARGUS_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    if sys.platform == "win32":
        return Path(sys.executable).parent
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Argus"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "argus"
