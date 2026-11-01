"""Active-window metadata used to scope captures and UI Automation."""

from __future__ import annotations

import os
import ctypes
from dataclasses import dataclass

from actions.screen_control.safety import is_blocked_process, is_blocked_terminal_window


@dataclass(frozen=True)
class WindowInfo:
    title: str
    process_name: str = ""
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0
    handle: int = 0

    @property
    def bounds(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.width, self.height


_ARGUS_PROCESS_NAMES = {"argus.exe"}


def set_thread_dpi_aware() -> None:
    """Use physical display pixels on the worker thread that captures and clicks."""
    if os.name != "nt":
        return
    try:
        # PER_MONITOR_AWARE_V2; it keeps Win32 geometry, MSS and PyAutoGUI aligned.
        ctypes.windll.user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            pass


def get_active_window(*, allow_argus: bool = False) -> WindowInfo:
    """Return the foreground window, failing closed when ARGUS owns focus."""
    set_thread_dpi_aware()
    try:
        import win32gui
        import win32process
        import psutil

        handle = int(win32gui.GetForegroundWindow() or 0)
        if not handle:
            raise RuntimeError("Não encontrei uma janela em primeiro plano.")
        title = str(win32gui.GetWindowText(handle) or "").strip()
        left, top, right, bottom = win32gui.GetWindowRect(handle)
        _, process_id = win32process.GetWindowThreadProcessId(handle)
        try:
            process_name = psutil.Process(process_id).name()
        except (psutil.Error, OSError):
            process_name = ""
        if is_blocked_terminal_window(title, process_name):
            raise RuntimeError("A janela do terminal é protegida e não pode ser alvo do controle de tela.")
        if not allow_argus and (
            process_id == os.getpid()
            or process_name.casefold() in _ARGUS_PROCESS_NAMES
            or "argus" in title.casefold()
        ):
            raise RuntimeError("A janela do ARGUS está em foco; coloque o aplicativo que deseja controlar em primeiro plano.")
        width, height = max(0, right - left), max(0, bottom - top)
        if width < 10 or height < 10:
            raise RuntimeError("A janela em foco não tem uma área utilizável.")
        return WindowInfo(title, process_name, left, top, width, height, handle)
    except ImportError as exc:
        raise RuntimeError("A captura de janela requer pywin32 e psutil no Windows.") from exc


def bring_to_front(title_or_process: str) -> bool:
    target = str(title_or_process or "").strip().casefold()
    if not target:
        return False
    try:
        import win32gui
        import win32con
        import psutil

        matches: list[tuple[int, int]] = []
        def collect(handle: int, _extra) -> None:
            if not win32gui.IsWindowVisible(handle):
                return
            title = str(win32gui.GetWindowText(handle) or "").strip().casefold()
            try:
                _, pid = __import__("win32process").GetWindowThreadProcessId(handle)
                process = psutil.Process(pid).name().casefold()
            except Exception:
                process = ""
            if (
                is_blocked_process(process)
                or is_blocked_terminal_window(title, process)
                or process == "argus.exe"
                or "argus" in title
            ):
                return
            process_stem = process.removesuffix(".exe")
            target_stem = target.removesuffix(".exe")
            aliases = {
                "google chrome": {"chrome"},
                "microsoft edge": {"msedge", "edge"},
                "brave browser": {"brave"},
                "mozilla firefox": {"firefox"},
                "firefox": {"firefox"},
                "opera": {"opera"},
                "opera gx": {"opera"},
                "vivaldi": {"vivaldi"},
                "visual studio code": {"code"},
                "microsoft teams": {"teams", "msteams"},
                "file explorer": {"explorer"},
            }
            exact_process = process_stem == target_stem or process_stem in aliases.get(target_stem, set())
            exact_title = title == target
            if exact_process or exact_title or target in title or target in process:
                # Prefer an exact title/process match over a substring match.
                rank = 0 if exact_title or exact_process else 1
                matches.append((rank, handle))
        win32gui.EnumWindows(collect, None)
        if not matches:
            return False
        matches.sort(key=lambda row: row[0])
        current_thread = __import__("win32api").GetCurrentThreadId()
        user32 = ctypes.windll.user32
        for _, handle in matches:
            foreground = int(win32gui.GetForegroundWindow() or 0)
            target_thread, _ = __import__("win32process").GetWindowThreadProcessId(handle)
            foreground_thread = (
                __import__("win32process").GetWindowThreadProcessId(foreground)[0]
                if foreground else 0
            )
            attached: list[int] = []
            try:
                for thread_id in {target_thread, foreground_thread} - {0, current_thread}:
                    if user32.AttachThreadInput(current_thread, thread_id, True):
                        attached.append(thread_id)
                win32gui.ShowWindow(handle, win32con.SW_RESTORE)
                win32gui.BringWindowToTop(handle)
                win32gui.SetForegroundWindow(handle)
                if int(win32gui.GetForegroundWindow() or 0) == handle:
                    return True
            finally:
                for thread_id in attached:
                    user32.AttachThreadInput(current_thread, thread_id, False)
        return False
    except Exception:
        return False
