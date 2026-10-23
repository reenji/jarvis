import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from config.user_config import (
    get_configured_gemini_key,
    load_user_config,
    save_user_config,
    store_gemini_key,
    user_config_path,
)


class UserConfigTests(unittest.TestCase):
    def test_config_is_private_and_round_trips(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Argus" / "config.yaml"
            config = {"llm": {"model": "gemini-test", "gemini_api_key": "secret-for-test"}}
            save_user_config(config, path=path)

            self.assertEqual(load_user_config(path=path), config)
            self.assertEqual(get_configured_gemini_key(config), "secret-for-test")
            if os.name != "nt":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_config_path_uses_argus_home_and_file_override(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"ARGUS_HOME": temp_dir, "ARGUS_CONFIG_FILE": ""}):
                self.assertEqual(user_config_path(), Path(temp_dir) / "config.yaml")
            custom_path = Path(temp_dir) / "custom.yaml"
            with patch.dict(os.environ, {"ARGUS_CONFIG_FILE": str(custom_path)}):
                self.assertEqual(user_config_path(), custom_path)

    def test_key_uses_file_when_system_keyring_is_unavailable(self):
        with patch("config.user_config.keyring_backend", return_value=None):
            config = {}
            storage = store_gemini_key(config, "key-for-test")
        self.assertEqual(storage, "user config file")
        self.assertEqual(get_configured_gemini_key(config), "key-for-test")
        self.assertEqual(config["llm"]["api_key_storage"], "config file")

    def test_key_uses_system_keyring_when_secure_backend_is_available(self):
        keyring = SimpleNamespace(set_password=Mock())
        config = {}
        with patch("config.user_config.keyring_backend", return_value=keyring):
            storage = store_gemini_key(config, "key-for-test")
        self.assertEqual(storage, "system keyring")
        self.assertNotIn("gemini_api_key", config["llm"])
        keyring.set_password.assert_called_once()
