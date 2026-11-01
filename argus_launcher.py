"""Single entry point for the packaged ARGUS app.

The Windows bundle ships two executables built from this script:

- ``ARGUS.exe`` (windowed) opens the desktop assistant on a double click.
- ``argus.com`` (console) runs the terminal CLI. ``cmd`` and PowerShell try
  ``.com`` before ``.exe`` (PATHEXT order), so typing ``argus chat`` in a
  terminal reaches the console build even though both sit in one folder.

``argus desktop`` opens the desktop window from a terminal, and the windowed
build hands any CLI arguments to its console sibling in a new console window.

On macOS and Linux one executable serves both: with no arguments it starts
the CLI in an interactive terminal and the desktop window otherwise (Finder,
Dock, an app menu entry).
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path


DESKTOP_COMMANDS = frozenset({"desktop", "app"})
CONSOLE_EXECUTABLE = "argus.com"


def choose_mode(argv: Sequence[str], *, has_console: bool, interactive: bool = True) -> str:
    """Return ``desktop``, ``cli`` or ``relaunch`` for the given arguments."""
    if argv and (argv[0] in DESKTOP_COMMANDS or argv[0] == "--self-test"):
        return "desktop"
    if not argv:
        return "cli" if has_console and interactive else "desktop"
    # Any other arguments belong to the CLI parser, which reports bad ones.
    return "cli" if has_console else "relaunch"


def _has_console() -> bool:
    # PyInstaller windowed builds run without standard streams.
    return sys.stdout is not None


def _interactive() -> bool:
    # Finder, the Dock and app menus start the app with no terminal attached.
    stdin = sys.stdin
    return stdin is not None and stdin.isatty()


def _run_desktop(argv: Sequence[str]) -> int:
    os.environ["ARGUS_CLI"] = "1"
    if not _has_console():
        # Windowed ARGUS.exe: without this, every PowerShell or nvidia-smi
        # probe the app runs opens a visible console window.
        from core.windows_console import hide_child_consoles

        hide_child_consoles()
    rest = list(argv[1:]) if argv and argv[0] in DESKTOP_COMMANDS else list(argv)
    sys.argv = [sys.argv[0], *rest]
    import main as desktop

    return desktop.main() or 0


def _run_cli(argv: Sequence[str]) -> int:
    from cli.app import main as cli_main

    return cli_main(list(argv))


def _relaunch_in_console(argv: Sequence[str]) -> int:
    console = Path(sys.executable).with_name(CONSOLE_EXECUTABLE)
    if not console.exists():
        return 2
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen([str(console), *argv], creationflags=flags)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    # Older macOS versions pass a process serial number when Finder opens an app.
    args = [arg for arg in args if not arg.startswith("-psn_")]
    mode = choose_mode(args, has_console=_has_console(), interactive=_interactive())
    if mode == "desktop":
        return _run_desktop(args)
    if mode == "relaunch":
        return _relaunch_in_console(args)
    return _run_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
