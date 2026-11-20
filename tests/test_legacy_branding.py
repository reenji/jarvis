import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIRS = ("actions", "agent", "cli", "core", "ui")
LEGACY_NAMES = re.compile(r"J\.A\.R\.V\.I\.S|MARK XXXIX")


class LegacyBrandingTests(unittest.TestCase):
    def test_app_code_does_not_show_legacy_names(self):
        hits = []
        for folder in APP_DIRS:
            for path in sorted((ROOT / folder).rglob("*.py")):
                text = path.read_text(encoding="utf-8")
                for number, line in enumerate(text.splitlines(), start=1):
                    if LEGACY_NAMES.search(line):
                        hits.append(f"{path.relative_to(ROOT)}:{number}")

        self.assertEqual(hits, [], "legacy branding found: " + ", ".join(hits))


if __name__ == "__main__":
    unittest.main()
