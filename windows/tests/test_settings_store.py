from __future__ import annotations

import unittest
from dataclasses import fields
from pathlib import Path

import codexcontrol_windows.settings_store as settings_store
from codexcontrol_windows.overlay_geometry import DockEdge, OverlayPlacement, Point
from codexcontrol_windows.settings_store import (
    OverlaySettings,
    OverlaySettingsStore,
    overlay_settings_with_topmost,
    overlay_settings_with_visibility,
)


class OverlaySettingsStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("test-artifacts") / "settings-store"
        self.root.mkdir(parents=True, exist_ok=True)
        for path in self.root.glob("*"):
            path.unlink()

    def tearDown(self) -> None:
        for path in self.root.glob("*"):
            path.unlink()
        try:
            self.root.rmdir()
            self.root.parent.rmdir()
        except OSError:
            pass

    def test_round_trip_preserves_placement_and_behavior(self) -> None:
        self.assertIn("quota_mode", {field.name for field in fields(OverlaySettings)})
        path = self.root / "settings.json"
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
            always_on_top=False,
            quota_mode="7d",
        )

        store.save(expected)
        restored = store.load()

        self.assertEqual(restored, expected)
        self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_missing_file_returns_safe_defaults(self) -> None:
        restored = OverlaySettingsStore(self.root / "missing.json").load()

        self.assertTrue(restored.overlay_enabled)
        self.assertTrue(restored.auto_hide)
        self.assertTrue(restored.always_on_top)
        self.assertEqual(getattr(restored, "quota_mode", None), "5h")
        self.assertIsNone(restored.placement)

    def test_malformed_file_returns_defaults_without_overwriting_it(self) -> None:
        path = self.root / "settings.json"
        path.write_text("not-json", encoding="utf-8")

        restored = OverlaySettingsStore(path).load()

        self.assertIsNone(restored.placement)
        self.assertEqual(path.read_text(encoding="utf-8"), "not-json")

    def test_visibility_update_preserves_placement_and_auto_hide(self) -> None:
        placement = OverlayPlacement(
            monitor_name="DISPLAY2",
            normalized_x=1.0,
            normalized_y=0.4,
            position=Point(2500, 400),
            edge=DockEdge.RIGHT,
        )
        settings = OverlaySettings(
            placement=placement,
            overlay_enabled=True,
            auto_hide=False,
            always_on_top=True,
        )

        updated = overlay_settings_with_visibility(settings, False)

        self.assertEqual(updated.placement, placement)
        self.assertFalse(updated.overlay_enabled)
        self.assertFalse(updated.auto_hide)
        self.assertTrue(updated.always_on_top)

    def test_topmost_update_preserves_other_behavior(self) -> None:
        settings = OverlaySettings(
            placement=None,
            overlay_enabled=False,
            auto_hide=False,
            always_on_top=True,
        )

        updated = overlay_settings_with_topmost(settings, False)

        self.assertFalse(updated.overlay_enabled)
        self.assertFalse(updated.auto_hide)
        self.assertFalse(updated.always_on_top)

    def test_quota_mode_update_preserves_other_behavior(self) -> None:
        self.assertTrue(hasattr(settings_store, "overlay_settings_with_quota_mode"))
        settings = OverlaySettings(
            placement=None,
            overlay_enabled=False,
            auto_hide=False,
            always_on_top=False,
            quota_mode="5h",
        )

        updated = settings_store.overlay_settings_with_quota_mode(settings, "7d")

        self.assertEqual(updated.quota_mode, "7d")
        self.assertFalse(updated.overlay_enabled)
        self.assertFalse(updated.auto_hide)
        self.assertFalse(updated.always_on_top)


if __name__ == "__main__":
    unittest.main()
