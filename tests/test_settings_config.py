import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config.user_config import save_user_config


class SettingsConfigTests(unittest.TestCase):
    def test_settings_load_user_preferences_and_keep_environment_key_precedence(self):
        from config.settings import get_api_key, get_settings

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "config.yaml"
            save_user_config(
                {
                    "llm": {"model": "gemini-user-model", "gemini_api_key": "file-key"},
                    "voice": {"enabled": True, "name": "kore"},
                },
                path=path,
            )
            with patch.dict(os.environ, {"ARGUS_CONFIG_FILE": str(path)}, clear=True):
                settings = get_settings()
                self.assertEqual(settings.llm.model, "gemini-user-model")
                self.assertTrue(settings.voice.enabled)
                self.assertEqual(settings.voice.name, "kore")
                self.assertEqual(get_api_key(), "file-key")
            with patch.dict(
                os.environ,
                {"ARGUS_CONFIG_FILE": str(path), "ARGUS_LLM_GEMINI_API_KEY": "env-key"},
                clear=True,
            ):
                self.assertEqual(get_api_key(), "env-key")
