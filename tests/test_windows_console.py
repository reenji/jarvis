from __future__ import annotations

import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import argus_launcher
from core import windows_console
from core.windows_console import CREATE_NEW_CONSOLE, CREATE_NO_WINDOW, DETACHED_PROCESS


ROOT = Path(__file__).resolve().parents[1]


class HiddenByDefaultTests(unittest.TestCase):
    def init_with(self, **kwargs):
        seen = {}

        def original(self, *args, creationflags=0, **rest):
            seen["flags"] = creationflags

        windows_console._hidden_by_default(original)(object(), ["probe"], **kwargs)
        return seen["flags"]

    def test_background_processes_get_no_window(self):
        self.assertEqual(self.init_with(), CREATE_NO_WINDOW)

    def test_other_flags_are_kept(self):
        new_group = 0x00000200
        self.assertEqual(self.init_with(creationflags=new_group), new_group | CREATE_NO_WINDOW)

    def test_an_explicit_console_choice_is_respected(self):
        for flags in (CREATE_NEW_CONSOLE, DETACHED_PROCESS, CREATE_NO_WINDOW):
            with self.subTest(flags=hex(flags)):
                self.assertEqual(self.init_with(creationflags=flags), flags)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(setattr, windows_console, "_installed", False)

    def test_does_nothing_outside_windows(self):
        original = subprocess.Popen.__init__
        with patch.object(sys, "platform", "linux"):
            self.assertFalse(windows_console.hide_child_consoles())
        self.assertIs(subprocess.Popen.__init__, original)

    def test_installs_once_on_windows(self):
        calls = []

        def fake_init(self, *args, creationflags=0, **kwargs):
            calls.append(creationflags)

        with patch.object(sys, "platform", "win32"), patch.object(subprocess.Popen, "__init__", fake_init):
            self.assertTrue(windows_console.hide_child_consoles())
            self.assertFalse(windows_console.hide_child_consoles())
            subprocess.Popen(["powershell", "-Command", "probe"])
        self.assertEqual(calls, [CREATE_NO_WINDOW])


class LauncherTests(unittest.TestCase):
    def run_desktop(self, *, has_console):
        fake_main = types.ModuleType("main")
        fake_main.main = lambda: 0
        with patch.object(argus_launcher, "_has_console", return_value=has_console), \
                patch.dict(sys.modules, {"main": fake_main}), \
                patch("core.windows_console.hide_child_consoles") as hide:
            self.assertEqual(argus_launcher._run_desktop([]), 0)
        return hide

    def test_windowed_desktop_hides_child_consoles(self):
        self.run_desktop(has_console=False).assert_called_once_with()

    def test_desktop_started_from_a_console_shares_it(self):
        self.run_desktop(has_console=True).assert_not_called()

    def test_apps_the_user_opens_get_a_visible_console(self):
        source = (ROOT / "actions" / "open_app.py").read_text(encoding="utf-8")
        self.assertIn('creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0)', source)


class WindowsTemperatureProbeTests(unittest.TestCase):
    def metrics(self):
        from ui.hud.metrics import _SysMetrics

        metrics = _SysMetrics.__new__(_SysMetrics)
        metrics._win_temp_available = True
        metrics._win_temp_value = -1.0
        metrics._win_temp_read_at = 0.0
        return metrics

    def test_a_failing_probe_is_not_retried(self):
        metrics = self.metrics()
        run = MagicMock(return_value=MagicMock(returncode=1, stdout=""))
        with patch("ui.hud.metrics.subprocess.run", run):
            self.assertEqual(metrics._get_windows_temp(), -1.0)
            self.assertEqual(metrics._get_windows_temp(), -1.0)
        run.assert_called_once()

    def test_a_working_probe_is_cached_between_reads(self):
        metrics = self.metrics()
        run = MagicMock(return_value=MagicMock(returncode=0, stdout="3231\n"))
        with patch("ui.hud.metrics.subprocess.run", run):
            first = metrics._get_windows_temp()
            second = metrics._get_windows_temp()
        self.assertAlmostEqual(first, 49.95, places=2)
        self.assertEqual(second, first)
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
