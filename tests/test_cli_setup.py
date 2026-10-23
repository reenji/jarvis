import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cli.setup import ApiProbe, run_setup, validate_gemini_key
from config.user_config import get_configured_gemini_key, load_user_config


class SetupTests(unittest.TestCase):
    def test_api_probe_redacts_raw_network_error_text(self):
        with patch("google.genai.Client", side_effect=TimeoutError("secret-key and private URL")):
            result = validate_gemini_key("secret-key")
        self.assertFalse(result.ok)
        self.assertIn("timed out", result.message)
        self.assertNotIn("secret-key", result.message)
        self.assertNotIn("private URL", result.message)

    def test_setup_skips_hidden_key_prompt_when_environment_key_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = []
            secret_prompt = Mock(side_effect=AssertionError("must not ask for an env key"))
            with patch.dict(
                os.environ,
                {
                    "ARGUS_CONFIG_FILE": str(Path(temp_dir) / "config.yaml"),
                    "ARGUS_LLM_GEMINI_API_KEY": "env-secret-for-test",
                },
            ):
                result = run_setup(
                    input_fn=lambda _prompt: "n",
                    secret_input_fn=secret_prompt,
                    api_probe=lambda _key: ApiProbe(True, "verified"),
                    output=output.append,
                )
            self.assertEqual(result, 0)
            secret_prompt.assert_not_called()
            saved = load_user_config(path=Path(temp_dir) / "config.yaml")
            self.assertNotIn("gemini_api_key", saved.get("llm", {}))
            self.assertNotIn("env-secret-for-test", "\n".join(output))

    def test_setup_hides_and_validates_new_key_before_saving(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = []
            with patch.dict(
                os.environ,
                {
                    "ARGUS_CONFIG_FILE": str(Path(temp_dir) / "config.yaml"),
                    "ARGUS_LLM_GEMINI_API_KEY": "",
                    "GEMINI_API_KEY": "",
                },
            ):
                result = run_setup(
                    input_fn=lambda _prompt: "n",
                    secret_input_fn=lambda _prompt: "new-secret-for-test",
                    api_probe=lambda key: ApiProbe(key == "new-secret-for-test", "verified"),
                    output=output.append,
                )
            self.assertEqual(result, 0)
            saved = load_user_config(path=Path(temp_dir) / "config.yaml")
            self.assertEqual(get_configured_gemini_key(saved), "new-secret-for-test")
            self.assertNotIn("new-secret-for-test", "\n".join(output))
