from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

import argus_launcher
from argus_launcher import choose_mode


class LauncherModeTests(unittest.TestCase):
    def test_double_click_opens_the_desktop_window(self):
        self.assertEqual(choose_mode([], has_console=False), "desktop")

    def test_bare_command_in_a_terminal_starts_the_cli(self):
        self.assertEqual(choose_mode([], has_console=True), "cli")

    def test_bare_command_without_a_terminal_opens_the_desktop_window(self):
        # Finder, the Dock or a Linux app menu: streams exist but no terminal.
        self.assertEqual(choose_mode([], has_console=True, interactive=False), "desktop")

    def test_cli_arguments_run_even_without_a_terminal(self):
        self.assertEqual(choose_mode(["ask", "oi"], has_console=True, interactive=False), "cli")

    def test_cli_arguments_run_in_the_console_build(self):
        for argv in (["chat"], ["setup"], ["doctor"], ["--version"], ["-q", "oi"], ["ask", "oi"]):
            with self.subTest(argv=argv):
                self.assertEqual(choose_mode(argv, has_console=True), "cli")

    def test_windowed_build_hands_cli_arguments_to_the_console_build(self):
        self.assertEqual(choose_mode(["chat"], has_console=False), "relaunch")

    def test_desktop_command_opens_the_window_from_either_build(self):
        for command in ("desktop", "app"):
            for has_console in (True, False):
                with self.subTest(command=command, has_console=has_console):
                    self.assertEqual(choose_mode([command], has_console=has_console), "desktop")

    def test_self_test_stays_with_the_desktop_entry_point(self):
        self.assertEqual(choose_mode(["--self-test"], has_console=True), "desktop")


class LauncherDispatchTests(unittest.TestCase):
    def test_cli_mode_forwards_arguments_unchanged(self):
        with patch.object(argus_launcher, "_has_console", return_value=True), \
                patch.object(argus_launcher, "_interactive", return_value=True), \
                patch("cli.app.main", return_value=0) as cli_main:
            self.assertEqual(argus_launcher.main(["ask", "oi"]), 0)
        cli_main.assert_called_once_with(["ask", "oi"])

    def test_finder_process_serial_number_is_ignored(self):
        with patch.object(argus_launcher, "_has_console", return_value=True), \
                patch.object(argus_launcher, "_interactive", return_value=False), \
                patch.object(argus_launcher, "_run_desktop", return_value=0) as run_desktop:
            self.assertEqual(argus_launcher.main(["-psn_0_12345"]), 0)
        run_desktop.assert_called_once_with([])

    def test_relaunch_fails_cleanly_without_the_console_build(self):
        with patch.object(argus_launcher.sys, "executable", str(Path("/nonexistent/ARGUS.exe"))), \
                patch.object(argus_launcher.subprocess, "Popen") as popen:
            self.assertEqual(argus_launcher._relaunch_in_console(["chat"]), 2)
        popen.assert_not_called()

    def test_relaunch_starts_the_console_build_with_the_same_arguments(self):
        with patch.object(argus_launcher.Path, "exists", return_value=True), \
                patch.object(argus_launcher.subprocess, "Popen") as popen:
            self.assertEqual(argus_launcher._relaunch_in_console(["chat"]), 0)
        command = popen.call_args.args[0]
        self.assertEqual(Path(command[0]).name, "argus.com")
        self.assertEqual(command[1:], ["chat"])


if __name__ == "__main__":
    unittest.main()
