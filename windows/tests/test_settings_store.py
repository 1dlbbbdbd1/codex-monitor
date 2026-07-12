from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from codexcontrol_windows.overlay_geometry import DockEdge, OverlayPlacement, Point
from codexcontrol_windows.settings_store import OverlaySettings, OverlaySettingsStore


class OverlaySettingsStoreTests(unittest.TestCase):
    def test_round_trip_preserves_placement_and_behavior(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            store = OverlaySettingsStore(path)
            expected = OverlaySettings(
                placement=OverlayPlacement(
                    monitor_name="DISPLAY2",
                    normalized_x=1.0,
                    normalized_y=0.4,
                    position=Point(2500, 400),
                    edge=DockEdge.RIGHT,
                ),
                overlay_enabled=True,
                auto_hide=True,
            )

            store.save(expected)
            restored = store.load()

            self.assertEqual(restored, expected)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_missing_file_returns_safe_defaults(self) -> None:
        with TemporaryDirectory() as temp_dir:
            restored = OverlaySettingsStore(Path(temp_dir) / "missing.json").load()

            self.assertTrue(restored.overlay_enabled)
            self.assertTrue(restored.auto_hide)
            self.assertIsNone(restored.placement)

    def test_malformed_file_returns_defaults_without_overwriting_it(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "settings.json"
            path.write_text("not-json", encoding="utf-8")

            restored = OverlaySettingsStore(path).load()

            self.assertIsNone(restored.placement)
            self.assertEqual(path.read_text(encoding="utf-8"), "not-json")


if __name__ == "__main__":
    unittest.main()
