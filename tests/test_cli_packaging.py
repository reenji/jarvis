from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliPackagingMetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    def test_cli_entry_point_and_python_floor_are_declared(self):
        self.assertEqual(self.project["requires-python"], ">=3.11")
        self.assertEqual(self.project["scripts"]["argus"], "cli.app:main")

    def test_base_install_contains_text_and_local_control_runtime(self):
        dependencies = set(self.project["dependencies"])
        self.assertTrue(
            {
                "google-genai",
                "keyring",
                "mss",
                "Pillow",
                "prompt-toolkit>=3,<4",
                "psutil",
                "pydantic>=2,<3",
                "pydantic-settings>=2,<3",
                "PyAutoGUI",
                "PyYAML>=6,<7",
                "pygetwindow",
                "pyperclip",
            }.issubset(dependencies)
        )
        self.assertFalse(any("PyQt" in dependency for dependency in dependencies))

    def test_optional_groups_keep_audio_browser_documents_integrations_and_api_separate(self):
        extras = self.project["optional-dependencies"]
        self.assertEqual(set(extras), {"voice", "browser", "documents", "integrations", "tts", "api"})
        self.assertEqual(set(extras["voice"]), {"numpy", "sounddevice"})
        self.assertIn("playwright", extras["browser"])
        self.assertIn("python-docx", extras["documents"])
        self.assertIn("google-api-python-client", extras["integrations"])
        self.assertTrue(any(dependency.startswith("fastapi") for dependency in extras["api"]))
        self.assertTrue(any(dependency.startswith("SQLAlchemy") for dependency in extras["api"]))

    def test_live_prompt_is_included_in_the_wheel(self):
        self.assertIn("prompt.txt", self.project_package_data("core"))

    def test_installers_cover_supported_shells_and_keep_voice_opt_in(self):
        bash = (ROOT / "scripts" / "install.sh").read_text(encoding="utf-8")
        powershell = (ROOT / "scripts" / "install.ps1").read_text(encoding="utf-8")
        for installer in (bash, powershell):
            self.assertIn("git+https://github.com/reenji/jarvis.git", installer)
            self.assertIn("[voice]", installer)
            self.assertIn("argus setup", installer)
        self.assertIn("uv", bash)
        self.assertIn("pipx", bash)
        self.assertIn("[switch]$Voice", powershell)

    @staticmethod
    def project_package_data(package: str) -> list[str]:
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        return data["tool"]["setuptools"]["package-data"][package]


if __name__ == "__main__":
    unittest.main()
