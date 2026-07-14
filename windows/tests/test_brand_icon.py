from __future__ import annotations

import unittest

import codexcontrol_windows.brand_icon as brand_icon
from codexcontrol_windows.brand_icon import build_orbit_dial_icon


class BrandIconTests(unittest.TestCase):
    def test_icon_matches_site_logo_palette_and_shape(self) -> None:
        image = build_orbit_dial_icon(64, accent="#3ad06d")

        center = image.getpixel((32, 32))
        self.assertGreater(center[0], center[1])
        self.assertGreater(center[0], center[2])
        self.assertGreater(center[3], 200)

        orbit_dot = image.getpixel((45, 23))
        self.assertGreater(orbit_dot[1], orbit_dot[0])
        self.assertGreater(orbit_dot[1], orbit_dot[2])
        self.assertGreater(orbit_dot[3], 200)

        left_ring = image.getpixel((16, 32))
        self.assertGreater(left_ring[1], left_ring[0])
        self.assertGreater(left_ring[1], left_ring[2])
        self.assertGreater(left_ring[3], 200)

        self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_icon_uses_antialiasing_on_outer_edge(self) -> None:
        image = build_orbit_dial_icon(56, accent="#31d18b", scale_factor=4)

        self.assertEqual(image.size, (56, 56))
        self.assertEqual(image.mode, "RGBA")
        alpha_values = {alpha for *_, alpha in image.getdata()}
        soft_alpha_values = {alpha for alpha in alpha_values if 0 < alpha < 255}

        self.assertGreater(len(soft_alpha_values), 8)

    def test_quota_dial_changes_with_remaining_percent(self) -> None:
        self.assertTrue(hasattr(brand_icon, "build_quota_dial_icon"))

        empty = brand_icon.build_quota_dial_icon(56, remaining_percent=0, accent="#31d18b")
        partial = brand_icon.build_quota_dial_icon(56, remaining_percent=75, accent="#31d18b")

        self.assertNotEqual(empty.tobytes(), partial.tobytes())
        self.assertTrue(any(0 < alpha < 255 for *_, alpha in partial.getdata()))


if __name__ == "__main__":
    unittest.main()
