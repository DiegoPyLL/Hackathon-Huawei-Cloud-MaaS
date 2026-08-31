import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.maas_demo.dotenv import load_dotenv


class DotenvTests(unittest.TestCase):
    def test_loads_known_keys_and_ignores_unrelated_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "not dotenv syntax\nexport MAAS_MODE=live\nUNRELATED=value\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                load_dotenv(path)
                self.assertEqual(os.environ["MAAS_MODE"], "live")
                self.assertNotIn("UNRELATED", os.environ)

    def test_does_not_replace_exported_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("MAAS_MODE=live\n", encoding="utf-8")
            with patch.dict(os.environ, {"MAAS_MODE": "mock"}, clear=True):
                load_dotenv(path)
                self.assertEqual(os.environ["MAAS_MODE"], "mock")
