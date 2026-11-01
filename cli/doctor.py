"""Local setup diagnostics; never sends input events or saves screenshots."""

from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from dataclasses import dataclass
from collections.abc import Callable

from cli.history import default_database_path
from cli.setup import validate_gemini_key
from config.settings import get_api_key
from config.user_config import UserConfigError, load_user_config, user_config_path


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str
    critical: bool = False


def argus_version() -> str:
    try:
        return importlib.metadata.version("argus-mark-xxxix")
    except importlib.metadata.PackageNotFoundError:
        return "0.1.0"


def _python_check() -> DoctorCheck:
    version = platform.python_version()
    if sys.version_info >= (3, 11):
        return DoctorCheck("Python", "ok", f"{version} (requires 3.11 or newer).")
    return DoctorCheck("Python", "fail", f"{version} is too old; install Python 3.11 or newer.", True)


def _config_check() -> DoctorCheck:
    path = user_config_path()
    if not path.exists():
        return DoctorCheck("User config", "skip", f"No file at {path}; environment variables may still configure ARGUS.")
    try:
        load_user_config(path=path)
    except UserConfigError as exc:
        return DoctorCheck("User config", "fail", f"{exc} Run `argus setup` after fixing the file.", True)
    return DoctorCheck("User config", "ok", f"Readable: {path} (secret values are not displayed).")


def _api_check() -> DoctorCheck:
    try:
        key = get_api_key()
    except (ValueError, UserConfigError):
        return DoctorCheck("Gemini API", "fail", "No usable API key found; run `argus setup` or set GEMINI_API_KEY.", True)
    result = validate_gemini_key(key)
    return DoctorCheck("Gemini API", "ok" if result.ok else "fail", result.message, True)


def _sqlite_check() -> DoctorCheck:
    database_path = default_database_path()
    temporary_path: Path | None = None
    try:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=database_path.parent,
            prefix=".argus-doctor-",
            suffix=".sqlite3",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
        probe_path = database_path if database_path.exists() else temporary_path
        connection = sqlite3.connect(probe_path, timeout=2)
        try:
            if database_path.exists():
                # Acquire a write reservation and inspect the existing DB without
                # running session-store cleanup or changing conversation data.
                connection.execute("BEGIN IMMEDIATE")
            else:
                connection.execute("CREATE TABLE doctor_probe (value INTEGER)")
                connection.execute("INSERT INTO doctor_probe VALUES (1)")
                connection.commit()
            result = connection.execute("PRAGMA quick_check").fetchone()
            if not result or result[0] != "ok":
                raise sqlite3.DatabaseError("SQLite integrity check failed")
            if database_path.exists():
                connection.rollback()
        finally:
            connection.close()
        return DoctorCheck("SQLite storage", "ok", f"Writable: {database_path.parent}.", True)
    except (OSError, sqlite3.Error) as exc:
        # Report the error class only; filesystem paths and raw messages can contain private details.
        return DoctorCheck("SQLite storage", "fail", f"Cannot write a SQLite database ({type(exc).__name__}); check the storage directory.", True)
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def _screen_check() -> DoctorCheck:
    try:
        import mss

        with mss.mss() as capture:
            monitors = capture.monitors
            if len(monitors) <= 1:
                return DoctorCheck("Screen capture", "fail", "No display was detected; check the desktop session permissions.")
            capture.grab(monitors[0])
        return DoctorCheck("Screen capture", "ok", "Captured a frame in memory; no screenshot was saved.")
    except ImportError:
        return DoctorCheck("Screen capture", "fail", "The screenshot package is missing; repair the ARGUS base installation.")
    except Exception as exc:
        return DoctorCheck("Screen capture", "fail", f"Capture unavailable ({type(exc).__name__}); check display and screen-recording permissions.")


def _input_check() -> DoctorCheck:
    system = platform.system()
    if system == "Linux" and (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE", "").casefold() == "wayland"):
        return DoctorCheck("Mouse and keyboard", "skip", "Screen control currently requires the Windows desktop backend; text mode and app launching remain available.")
    if system != "Windows":
        return DoctorCheck(
            "Mouse and keyboard",
            "skip",
            "Window focus, capture, and screen input currently use the Windows desktop backend; app launching and text mode remain available.",
        )
    try:
        import pyautogui

        pyautogui.position()  # Read-only probe; never click or type during doctor.
    except ImportError:
        return DoctorCheck("Mouse and keyboard", "fail", "The input automation package is missing; repair the ARGUS base installation.")
    except Exception as exc:
        return DoctorCheck("Mouse and keyboard", "fail", f"Input toolkit unavailable ({type(exc).__name__}); check desktop permissions.")
    return DoctorCheck("Mouse and keyboard", "ok", "Toolkit can read the pointer; doctor did not send a click or keystroke.")


def _audio_check() -> DoctorCheck:
    try:
        import sounddevice as sd
    except ImportError:
        return DoctorCheck("Audio devices", "skip", "Optional voice dependencies are not installed.")
    try:
        devices = sd.query_devices()
    except Exception as exc:
        return DoctorCheck("Audio devices", "fail", f"Could not list audio devices ({type(exc).__name__}); check the audio driver.")
    inputs = [str(device.get("name", "unknown")) for device in devices if int(device.get("max_input_channels", 0)) > 0]
    outputs = [str(device.get("name", "unknown")) for device in devices if int(device.get("max_output_channels", 0)) > 0]
    if not inputs or not outputs:
        return DoctorCheck("Audio devices", "fail", f"Input devices: {len(inputs)}; output devices: {len(outputs)}. Connect or enable a microphone and speaker.")
    return DoctorCheck("Audio devices", "ok", f"Input devices: {len(inputs)}; output devices: {len(outputs)}.")


def _terminal_check() -> DoctorCheck:
    encoding = sys.stdout.encoding or "unknown"
    utf8 = encoding.casefold().replace("-", "") == "utf8"
    color = bool(sys.stdout.isatty() and os.environ.get("NO_COLOR") is None and os.environ.get("TERM", "").casefold() != "dumb")
    size = shutil.get_terminal_size(fallback=(0, 0))
    detail = f"UTF-8: {'yes' if utf8 else 'no'}; color: {'yes' if color else 'no'}; size: {size.columns}x{size.lines}."
    status = "ok" if utf8 and size.columns >= 60 and size.lines >= 12 else "fail"
    if status == "fail":
        detail += " Use a UTF-8 terminal at least 60 columns by 12 lines for full CLI output."
    return DoctorCheck("Terminal", status, detail)


def collect_checks() -> list[DoctorCheck]:
    checks = [
        DoctorCheck("ARGUS", "ok", f"version {argus_version()}"),
        _python_check(),
        _config_check(),
        _api_check(),
        _sqlite_check(),
        _screen_check(),
        _input_check(),
        _audio_check(),
        _terminal_check(),
    ]
    return checks


def run_doctor(output: Callable[[str], None] = print) -> int:
    encoding = (sys.stdout.encoding or "").casefold().replace("-", "")
    supports_unicode = encoding == "utf8"
    glyphs = {"ok": "✓" if supports_unicode else "[OK]", "fail": "✗" if supports_unicode else "[FAIL]", "skip": "-"}
    output(f"ARGUS doctor — version {argus_version()} — Python {platform.python_version()}")
    checks = collect_checks()
    for check in checks:
        output(f"{glyphs[check.status]} {check.name}: {check.detail}")
    critical_failures = [check for check in checks if check.critical and check.status == "fail"]
    if critical_failures:
        output(f"{len(critical_failures)} critical check(s) failed. See the correction hints above.")
        return 1
    output("Critical checks passed. Review optional desktop and audio capabilities before using them.")
    return 0
