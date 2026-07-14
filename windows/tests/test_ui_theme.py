from __future__ import annotations

import unittest

from codexcontrol_windows.ui_theme import CODEX_DARK_PALETTE, contrast_ratio


class CodexLightPaletteTests(unittest.TestCase):
    def test_codex_theme_uses_the_product_light_palette(self) -> None:
        self.assertEqual(CODEX_DARK_PALETTE["bg"], "#ffffff")
        self.assertEqual(CODEX_DARK_PALETTE["text"], "#1a1c1f")
        self.assertEqual(CODEX_DARK_PALETTE["accent"], "#339cff")

    def test_primary_and_muted_text_have_readable_contrast(self) -> None:
        self.assertGreaterEqual(contrast_ratio(CODEX_DARK_PALETTE["text"], CODEX_DARK_PALETTE["shell"]), 7.0)
        self.assertGreaterEqual(contrast_ratio(CODEX_DARK_PALETTE["muted"], CODEX_DARK_PALETTE["shell"]), 4.5)

    def test_panel_text_is_legible(self) -> None:
        self.assertGreaterEqual(contrast_ratio(CODEX_DARK_PALETTE["text"], CODEX_DARK_PALETTE["panel"]), 7.0)


if __name__ == "__main__":
    unittest.main()
