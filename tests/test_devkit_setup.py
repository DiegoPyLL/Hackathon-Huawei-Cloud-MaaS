import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "ejecutablesBase"
    / "configurar-devkit-huawei.py"
)
SPEC = importlib.util.spec_from_file_location("configurar_devkit_huawei", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
DEVKIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEVKIT)


class ClaudeMcpConfigTests(unittest.TestCase):
    def test_shared_config_uses_environment_references(self):
        config = DEVKIT.claude_mcp_config(native_windows=False)

        self.assertEqual(config["command"], "npx")
        self.assertIn("huaweicloud-devkit@1.0.2", config["args"])
        self.assertEqual(
            config["env"],
            {
                "HW_ACCESS_KEY": "${HW_ACCESS_KEY:-}",
                "HW_SECRET_KEY": "${HW_SECRET_KEY:-}",
                "HW_REGION": "${HW_REGION:-}",
            },
        )

    def test_windows_config_runs_npx_through_cmd(self):
        config = DEVKIT.claude_mcp_config(native_windows=True)

        self.assertEqual(config["command"], "cmd")
        self.assertEqual(config["args"][:2], ["/c", "npx"])

    def test_auto_target_selects_only_installed_client(self):
        def find_executable(name):
            return "claude.exe" if name == "claude" else None

        with mock.patch.object(DEVKIT.shutil, "which", side_effect=find_executable):
            self.assertEqual(DEVKIT.resolve_target("auto"), "claude")

    def test_update_preserves_other_servers_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / ".mcp.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "existing": {"command": "existing-server", "args": []}
                        }
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(DEVKIT, "CLAUDE_CONFIG", config_path):
                self.assertTrue(DEVKIT.update_claude_config(dry_run=False))
                self.assertFalse(DEVKIT.update_claude_config(dry_run=False))

            document = json.loads(config_path.read_text(encoding="utf-8"))
            self.assertIn("existing", document["mcpServers"])
            self.assertEqual(
                document["mcpServers"]["huaweicloud-devkit"],
                DEVKIT.claude_mcp_config(),
            )

    def test_dry_run_does_not_create_file(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / ".mcp.json"

            with mock.patch.object(DEVKIT, "CLAUDE_CONFIG", config_path):
                self.assertTrue(DEVKIT.update_claude_config(dry_run=True))

            self.assertFalse(config_path.exists())

    def test_update_rejects_unmanaged_name_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / ".mcp.json"
            config_path.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "huaweicloud-devkit": {
                                "command": "different-program",
                                "args": [],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            with mock.patch.object(DEVKIT, "CLAUDE_CONFIG", config_path):
                with self.assertRaises(DEVKIT.SetupError):
                    DEVKIT.update_claude_config(dry_run=False)

    def test_claude_target_does_not_require_codex(self):
        arguments = SimpleNamespace(
            target="claude",
            auth=False,
            skip_koocli=True,
            dry_run=False,
        )

        with (
            mock.patch.object(DEVKIT, "parse_args", return_value=arguments),
            mock.patch.object(DEVKIT, "check_node", return_value=("node", "v22.0.0")),
            mock.patch.object(DEVKIT, "executable", return_value="npx"),
            mock.patch.object(
                DEVKIT, "check_claude", return_value=("claude", "2.1.220")
            ),
            mock.patch.object(DEVKIT, "check_codex") as check_codex,
            mock.patch.object(DEVKIT, "update_claude_config", return_value=False),
            mock.patch.object(DEVKIT, "run") as run,
        ):
            self.assertEqual(DEVKIT.main(), 0)

        check_codex.assert_not_called()
        run.assert_called_once_with(["claude", "mcp", "list"], dry_run=False)


if __name__ == "__main__":
    unittest.main()
