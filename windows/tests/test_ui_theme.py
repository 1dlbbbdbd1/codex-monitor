from __future__ import annotations

import unittest

from codexcontrol_windows.ui_theme import CODEX_DARK_PALETTE, contrast_ratio


class CodexDarkPaletteTests(unittest.TestCase):
    def test_primary_and_muted_text_have_readable_contrast(self) -> None:
        self.assertGreaterEqual(contrast_ratio(CODEX_DARK_PALETTE["text"], CODEX_DARK_PALETTE["shell"]), 7.0)
        self.assertGreaterEqual(contrast_ratio(CODEX_DARK_PALETTE["muted"], CODEX_DARK_PALETTE["shell"]), 4.5)

    def test_panel_text_and_accent_are_legible(self) -> None:
        self.assertGreaterEqual(contrast_ratio(CODEX_DARK_PALETTE["text"], CODEX_DARK_PALETTE["panel"]), 7.0)
        self.assertGreaterEqual(contrast_ratio(CODEX_DARK_PALETTE["accent"], CODEX_DARK_PALETTE["panel"]), 3.0)


if __name__ == "__main__":
    unittest.main()
