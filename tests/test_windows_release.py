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
        cls.workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
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

    def test_release_waits_for_every_platform(self):
        self.assertIn("needs: [windows, linux, macos]", self.workflow)


class MacosLinuxReleaseNameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.linux = (ROOT / "scripts" / "package_linux.sh").read_text(encoding="utf-8")
        cls.macos = (ROOT / "scripts" / "package_macos.sh").read_text(encoding="utf-8")

    def test_linux_packages_are_built_uploaded_and_linked(self):
        for name in ("ARGUS-linux-x86_64.deb", "ARGUS-linux-x86_64.tar.gz"):
            with self.subTest(name=name):
                self.assertIn(f'"$out/{name}"', self.linux)
                self.assertIn(f"dist/{name}", self.workflow)
                self.assertIn(f"{LATEST}{name}", self.readme)

    def test_macos_disk_image_is_built_uploaded_and_linked(self):
        name = "ARGUS-macos-arm64.dmg"
        self.assertIn(f'"$out/{name}"', self.macos)
        self.assertIn(f"dist/{name}", self.workflow)
        self.assertIn(f"{LATEST}{name}", self.readme)

    def test_linux_menu_entry_opens_the_desktop_window(self):
        self.assertIn("Exec=/usr/lib/argus/ARGUS desktop", self.linux)
        self.assertIn("ln -s ../lib/argus/ARGUS", self.linux)

    def test_macos_bundle_declares_microphone_use_and_version(self):
        spec = (ROOT / "ARGUS.spec").read_text(encoding="utf-8")
        self.assertIn("'NSMicrophoneUsageDescription'", spec)
        self.assertIn("'CFBundleShortVersionString': VERSION", spec)



class AppIconTests(unittest.TestCase):
    def test_icon_is_built_from_the_square_pixel_art(self):
        from PIL import Image

        art = Image.open(ROOT / "assets" / "argus-icon.png")
        self.assertEqual(art.width, art.height)
        icon = Image.open(ROOT / "assets" / "argus.ico")
        self.assertEqual(
            sorted(icon.info["sizes"]),
            [(size, size) for size in (16, 24, 32, 48, 64, 128, 256)],
        )

    def test_executables_installer_and_window_share_the_icon(self):
        spec = (ROOT / "ARGUS.spec").read_text(encoding="utf-8")
        self.assertIn("icon='assets/argus.ico'", spec)
        self.assertIn("('assets/argus.ico', 'assets')", spec)
        self.assertIn(r"SetupIconFile=..\assets\argus.ico", (ROOT / "installer" / "argus.iss").read_text(encoding="utf-8"))
        runtime = (ROOT / "ui" / "_runtime.py").read_text(encoding="utf-8")
        self.assertIn('APP_ICON_FILE = BASE_DIR / "assets" / "argus.ico"', runtime)

if __name__ == "__main__":
    unittest.main()
