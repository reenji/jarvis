import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cli.app import build_parser
from cli.config_commands import set_config_value, show_config


class ConfigCommandTests(unittest.TestCase):
    def test_config_show_redacts_secret_and_config_set_blocks_api_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = []
            settings = SimpleNamespace(
                llm=SimpleNamespace(gemini_api_key="secret-for-test", model="gemini-test"),
                voice=SimpleNamespace(enabled=False, name="puck"),
            )
            with patch.dict("os.environ", {"ARGUS_CONFIG_FILE": str(Path(temp_dir) / "config.yaml")}):
                with patch("cli.config_commands.get_settings", return_value=settings):
                    self.assertEqual(show_config(output.append), 0)
                    self.assertEqual(set_config_value("llm.gemini_api_key", "secret-for-test", output.append), 2)
            self.assertNotIn("secret-for-test", "\n".join(output))

    def test_config_set_persists_supported_values(self):
        from config.user_config import load_user_config

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            output = []
            with patch.dict("os.environ", {"ARGUS_CONFIG_FILE": str(path)}):
                self.assertEqual(set_config_value("voice.enabled", "yes", output.append), 0)
                self.assertEqual(set_config_value("llm.model", "gemini-test", output.append), 0)
                saved = load_user_config()
            self.assertTrue(saved["voice"]["enabled"])
            self.assertEqual(saved["llm"]["model"], "gemini-test")
            self.assertTrue(all(str(path) in line for line in output))

    def test_parser_has_setup_doctor_and_config_commands(self):
        parser = build_parser()
        self.assertEqual(parser.parse_args(["setup"]).command, "setup")
        self.assertEqual(parser.parse_args(["doctor"]).command, "doctor")
        self.assertEqual(parser.parse_args(["config", "path"]).config_command, "path")
        args = parser.parse_args(["config", "set", "voice.enabled", "true"])
        self.assertEqual((args.key, args.value), ("voice.enabled", "true"))
