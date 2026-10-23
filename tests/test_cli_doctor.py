import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cli.doctor import DoctorCheck, _input_check, _sqlite_check, run_doctor


class DoctorTests(unittest.TestCase):
    def test_doctor_fails_on_critical_failure(self):
        checks = [
            DoctorCheck("Gemini API", "fail", "Run setup.", True),
            DoctorCheck("Audio devices", "skip", "Voice is optional."),
        ]
        output = []
        with patch("cli.doctor.collect_checks", return_value=checks):
            self.assertEqual(run_doctor(output.append), 1)
        self.assertTrue(any("Run setup." in line for line in output))

    def test_input_diagnostic_never_sends_mouse_or_keyboard_events(self):
        fake_input = SimpleNamespace(position=Mock(return_value=(10, 20)), click=Mock(), write=Mock(), press=Mock())
        with patch.dict(sys.modules, {"pyautogui": fake_input}):
            with patch("cli.doctor.platform.system", return_value="Windows"):
                check = _input_check()
        self.assertEqual(check.status, "ok")
        fake_input.position.assert_called_once_with()
        fake_input.click.assert_not_called()
        fake_input.write.assert_not_called()
        fake_input.press.assert_not_called()

    def test_sqlite_diagnostic_checks_writability_without_creating_a_session_db(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "state" / "sessions.sqlite3"
            with patch.dict(os.environ, {"ARGUS_SESSION_DB": str(database_path)}):
                check = _sqlite_check()
            self.assertEqual(check.status, "ok")
            self.assertFalse(database_path.exists())
            self.assertEqual(list(database_path.parent.iterdir()), [])
