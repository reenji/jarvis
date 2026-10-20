"""Resolve the user's default browser without opening it."""

from __future__ import annotations

import platform
import subprocess


def detect_default_browser() -> str:
    """Return the registered HTTP handler, with Chrome as a portable fallback."""
    try:
        system = platform.system()
        if system == "Windows":
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
            ) as key:
                prog_id = str(winreg.QueryValueEx(key, "ProgId")[0]).casefold()
            for marker, name in (
                ("brave", "brave"), ("edge", "edge"), ("firefox", "firefox"),
                ("operagx", "operagx"), ("opera gx", "operagx"),
                ("opera", "opera"), ("vivaldi", "vivaldi"),
                ("chrome", "chrome"),
            ):
                if marker in prog_id:
                    return name
        elif system == "Darwin":
            output = subprocess.run(
                ["defaults", "read", "com.apple.LaunchServices/com.apple.launchservices.secure", "LSHandlers"],
                capture_output=True, text=True, timeout=5,
            ).stdout.casefold()
            for marker, name in (
                ("brave", "brave"), ("edge", "edge"), ("firefox", "firefox"),
                ("operagx", "operagx"), ("opera gx", "operagx"),
                ("opera", "opera"), ("vivaldi", "vivaldi"),
                ("safari", "safari"), ("chrome", "chrome"),
            ):
                if marker in output:
                    return name
        elif system == "Linux":
            output = subprocess.run(
                ["xdg-settings", "get", "default-web-browser"],
                capture_output=True, text=True, timeout=5,
            ).stdout.casefold()
            for marker, name in (
                ("brave", "brave"), ("edge", "edge"), ("firefox", "firefox"),
                ("opera", "opera"), ("vivaldi", "vivaldi"), ("chrome", "chrome"),
            ):
                if marker in output:
                    return name
    except Exception:
        pass
    return "chrome"
