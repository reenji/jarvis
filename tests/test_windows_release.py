from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LATEST = "https://github.com/reenji/jarvis/releases/latest/download/"


class WindowsReleaseNameTests(unittest.TestCase):
    """The README and site link to releases/latest/download/<name>, so names must not drift."""

    @classmethod
    def setUpClass(cls):
        cls.installer = (ROOT / "installer" / "argus.iss").read_text(encoding="utf-8")
        cls.workflow = (ROOT / ".github" / "workflows" / "windows.yml").read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_installer_name_is_stable_and_uploaded(self):
        match = re.search(r"^OutputBaseFilename=(.+)$", self.installer, re.MULTILINE)
        self.assertIsNotNone(match)
        name = f"{match.group(1).strip()}.exe"
        self.assertNotIn("{#AppVersion}", name)
        self.assertIn(f"dist/{name}", self.workflow)
        self.assertIn(f"{LATEST}{name}", self.readme)

    def test_portable_zip_name_is_stable_and_uploaded(self):
        name = "ARGUS-windows-x64-portable.zip"
        self.assertIn(f"-DestinationPath dist\\{name}", self.workflow)
        self.assertIn(f"dist/{name}", self.workflow)
        self.assertIn(f"{LATEST}{name}", self.readme)

    def test_release_publishes_checksums_for_the_downloads(self):
        self.assertIn("sha256sum ARGUS-* > SHA256SUMS.txt", self.workflow)


if __name__ == "__main__":
    unittest.main()
