from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from codexcontrol_windows.hook_installer import HookInstallError, HookInstaller, count_companion_hooks


class HookInstallerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.hooks_path = self.root / ".codex" / "hooks.json"
        self.backup_dir = self.root / "backups"
        self.installer = HookInstaller(self.hooks_path, self.backup_dir)
        self.executable = self.root / "CodexFloatingCompanion.exe"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_install_preserves_unrelated_hooks_and_is_idempotent(self) -> None:
        self.hooks_path.parent.mkdir(parents=True)
        existing = {
            "description": "user hooks",
            "hooks": {
                "Stop": [
                    {
                        "matcher": None,
                        "hooks": [
                            {
                                "type": "command",
                                "command": "existing-tool",
                                "statusMessage": "Existing tool",
                            }
                        ],
                    }
                ]
            },
        }
        self.hooks_path.write_text(json.dumps(existing), encoding="utf-8")

        self.installer.install(self.executable)
        self.installer.install(self.executable)
        result = json.loads(self.hooks_path.read_text(encoding="utf-8"))

        self.assertEqual(result["description"], "user hooks")
        self.assertEqual(result["hooks"]["Stop"][0]["hooks"][0]["command"], "existing-tool")
        self.assertEqual(count_companion_hooks(result), 4)
        self.assertTrue(all("statusMessage" in handler for handler in companion_handlers(result)))

    def test_install_creates_backup_before_replacing_existing_file(self) -> None:
        self.hooks_path.parent.mkdir(parents=True)
        original = b'{"hooks": {}}'
        self.hooks_path.write_bytes(original)

        self.installer.install(self.executable)

        backups = list(self.backup_dir.glob("hooks.*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)

    def test_malformed_hooks_file_is_unchanged(self) -> None:
        self.hooks_path.parent.mkdir(parents=True)
        original = b"not-json"
        self.hooks_path.write_bytes(original)

        with self.assertRaises(HookInstallError):
            self.installer.install(self.executable)

        self.assertEqual(self.hooks_path.read_bytes(), original)
        self.assertEqual(list(self.backup_dir.glob("*")) if self.backup_dir.exists() else [], [])

    def test_uninstall_removes_only_companion_handlers(self) -> None:
        self.hooks_path.parent.mkdir(parents=True)
        self.hooks_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "Stop": [
                            {
                                "hooks": [
                                    {"type": "command", "command": "existing-tool", "statusMessage": "Existing"}
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        self.installer.install(self.executable)

        self.installer.uninstall()
        result = json.loads(self.hooks_path.read_text(encoding="utf-8"))

        self.assertEqual(count_companion_hooks(result), 0)
        self.assertEqual(result["hooks"]["Stop"][0]["hooks"][0]["command"], "existing-tool")


def companion_handlers(payload: dict[str, object]) -> list[dict[str, object]]:
    handlers: list[dict[str, object]] = []
    hooks = payload.get("hooks", {})
    if not isinstance(hooks, dict):
        return handlers
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            for handler in group.get("hooks", []):
                if isinstance(handler, dict) and str(handler.get("statusMessage", "")).startswith(
                    "Codex Floating Companion"
                ):
                    handlers.append(handler)
    return handlers


if __name__ == "__main__":
    unittest.main()
