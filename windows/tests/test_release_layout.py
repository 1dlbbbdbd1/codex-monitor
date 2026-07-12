from __future__ import annotations

import unittest
from pathlib import Path


WINDOWS_ROOT = Path(__file__).resolve().parents[1]


class ReleaseLayoutTests(unittest.TestCase):
    def test_scripts_use_companion_product_name_and_lifecycle_commands(self) -> None:
        build = (WINDOWS_ROOT / "build.ps1").read_text(encoding="utf-8")
        install = (WINDOWS_ROOT / "install.ps1").read_text(encoding="utf-8")
        package = (WINDOWS_ROOT / "package_release.ps1").read_text(encoding="utf-8")
        uninstall = (WINDOWS_ROOT / "uninstall.ps1").read_text(encoding="utf-8")

        self.assertIn("CodexFloatingCompanion", build)
        self.assertIn("--install-hooks", install)
        self.assertIn("--uninstall-hooks", uninstall)
        self.assertIn("CodexFloatingCompanion-windows-x64.zip", package)
        self.assertIn("$LASTEXITCODE", build)
        self.assertIn("$LASTEXITCODE", package)

    def test_release_package_includes_plugin_and_known_limitations(self) -> None:
        package = (WINDOWS_ROOT / "package_release.ps1").read_text(encoding="utf-8")

        self.assertIn("codex-floating-companion", package)
        self.assertIn("known-limitations.md", package)


if __name__ == "__main__":
    unittest.main()
