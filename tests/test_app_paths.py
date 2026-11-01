from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from core import app_paths


ROOT = Path(__file__).resolve().parents[1]


def frozen(platform: str, executable: str, meipass: str):
    return patch.multiple(
        sys,
        frozen=True,
        _MEIPASS=meipass,
        executable=executable,
        platform=platform,
        create=True,
    )


class SourceCheckoutPathTests(unittest.TestCase):
    def test_source_checkout_reads_and_writes_the_repository(self):
        self.assertEqual(app_paths.resource_dir(), ROOT)
        self.assertEqual(app_paths.data_dir(), ROOT)


class FrozenBuildPathTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("ARGUS_DATA_DIR", None)
        os.environ.pop("XDG_DATA_HOME", None)

    def test_windows_keeps_data_beside_the_executable(self):
        with frozen("win32", r"C:\Users\a\AppData\Local\Programs\Argus\ARGUS.exe", r"C:\Users\a\AppData\Local\Programs\Argus"):
            self.assertEqual(app_paths.data_dir(), Path(r"C:\Users\a\AppData\Local\Programs\Argus\ARGUS.exe").parent)
            self.assertEqual(app_paths.resource_dir(), Path(r"C:\Users\a\AppData\Local\Programs\Argus"))

    def test_macos_writes_to_application_support_and_reads_the_bundle(self):
        with frozen("darwin", "/Applications/ARGUS.app/Contents/MacOS/ARGUS", "/Applications/ARGUS.app/Contents/Frameworks"):
            self.assertEqual(app_paths.data_dir(), Path.home() / "Library" / "Application Support" / "Argus")
            self.assertEqual(app_paths.resource_dir(), Path("/Applications/ARGUS.app/Contents/Frameworks"))

    def test_linux_writes_to_the_xdg_data_folder(self):
        with frozen("linux", "/usr/lib/argus/ARGUS", "/usr/lib/argus"):
            self.assertEqual(app_paths.data_dir(), Path.home() / ".local" / "share" / "argus")
            os.environ["XDG_DATA_HOME"] = "/srv/data"
            self.assertEqual(app_paths.data_dir(), Path("/srv/data/argus"))

    def test_argus_data_dir_overrides_every_platform(self):
        os.environ["ARGUS_DATA_DIR"] = "~/argus-data"
        for platform in ("win32", "darwin", "linux"):
            with self.subTest(platform=platform), frozen(platform, "/opt/ARGUS", "/opt"):
                self.assertEqual(app_paths.data_dir(), Path("~/argus-data").expanduser())


class DataPathUsersTests(unittest.TestCase):
    def test_writable_files_follow_the_data_dir(self):
        import memory.memory_manager as memory_manager
        import memory.task_history as task_history

        self.assertEqual(memory_manager.MEMORY_PATH, app_paths.data_dir() / "memory" / "long_term.json")
        self.assertEqual(task_history.HISTORY_PATH, app_paths.data_dir() / "memory" / "task_history.json")

    def test_live_prompt_is_read_from_the_bundle(self):
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        self.assertIn('PROMPT_PATH     = resource_dir() / "core" / "prompt.txt"', source)


if __name__ == "__main__":
    unittest.main()
