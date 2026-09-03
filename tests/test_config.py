import os
import unittest
from unittest.mock import patch

from src.maas_demo.config import Config, ConfigError


class ConfigTests(unittest.TestCase):
    def test_mock_is_safe_default(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()

        self.assertEqual(config.mode, "mock")
        self.assertEqual(config.model, "deepseek-v4-pro")
        self.assertNotIn("chat/completions", config.base_url)

    def test_live_mode_requires_api_key(self) -> None:
        with patch.dict(os.environ, {"MAAS_MODE": "live"}, clear=True):
            with self.assertRaisesRegex(ConfigError, "MAAS_API_KEY"):
                Config.from_env()

    def test_invalid_mode_is_rejected(self) -> None:
        with patch.dict(os.environ, {"MAAS_MODE": "automatic"}, clear=True):
            with self.assertRaisesRegex(ConfigError, "mock.*live"):
                Config.from_env()
