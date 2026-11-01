"""Keep the windowed Windows app's child processes from opening console windows.

ARGUS.exe runs without a console. Windows gives every console program it
starts (PowerShell, nvidia-smi, cmd) a new, visible console window unless the
call says otherwise, so background probes flashed a PowerShell window every
few seconds. ``hide_child_consoles()`` makes CREATE_NO_WINDOW the default for
``subprocess`` on Windows. A call that wants a visible console, such as opening
PowerShell for the user, passes CREATE_NEW_CONSOLE and is left alone.
"""

from __future__ import annotations

import subprocess
import sys

# Win32 process-creation flags; subprocess only defines them on Windows.
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010
DETACHED_PROCESS = 0x00000008
_CONSOLE_CHOICES = CREATE_NO_WINDOW | CREATE_NEW_CONSOLE | DETACHED_PROCESS

_installed = False


def _hidden_by_default(original_init):
    def __init__(self, *args, creationflags=0, **kwargs):
        if not creationflags & _CONSOLE_CHOICES:
            creationflags |= CREATE_NO_WINDOW
        original_init(self, *args, creationflags=creationflags, **kwargs)

    __init__.__wrapped__ = original_init
    return __init__


def hide_child_consoles() -> bool:
    """Install the default once on Windows; return whether it was installed now."""
    global _installed
    if sys.platform != "win32" or _installed:
        return False
    subprocess.Popen.__init__ = _hidden_by_default(subprocess.Popen.__init__)
    _installed = True
    return True
