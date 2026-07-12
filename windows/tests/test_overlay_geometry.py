from __future__ import annotations

import unittest

from codexcontrol_windows.overlay_geometry import (
    DockEdge,
    Monitor,
    OverlayPlacement,
    Point,
    Rect,
    Size,
    dock_target,
    hidden_target,
    recover_to_monitors,
)


class HiddenGeometryTests(unittest.TestCase):
    def test_right_dock_keeps_twelve_pixel_handle_visible(self) -> None:
        work = Rect(0, 0, 1920, 1040)

        target = hidden_target(work, Size(56, 56), DockEdge.RIGHT, y=100, handle_px=12)

        self.assertEqual(target, Point(1908, 100))

    def test_left_dock_keeps_twelve_pixel_handle_visible(self) -> None:
        work = Rect(0, 0, 1920, 1040)

        target = hidden_target(work, Size(56, 56), DockEdge.LEFT, y=100, handle_px=12)

        self.assertEqual(target, Point(-44, 100))


class DockTargetTests(unittest.TestCase):
    def test_release_near_right_edge_docks_and_clamps_vertical_position(self) -> None:
        work = Rect(0, 0, 1920, 1040)

        placement = dock_target(work, Size(56, 56), Point(1900, 1030), monitor_name="DISPLAY1")

        self.assertEqual(placement.edge, DockEdge.RIGHT)
        self.assertEqual(placement.position, Point(1864, 984))
        self.assertEqual(placement.monitor_name, "DISPLAY1")

    def test_release_away_from_edges_remains_floating(self) -> None:
        work = Rect(0, 0, 1920, 1040)

        placement = dock_target(work, Size(56, 56), Point(500, 400), monitor_name="DISPLAY1")

        self.assertIsNone(placement.edge)
        self.assertEqual(placement.position, Point(500, 400))


class MonitorRecoveryTests(unittest.TestCase):
    def test_removed_monitor_recovers_window_to_primary_work_area(self) -> None:
        saved = OverlayPlacement(
            monitor_name="DISPLAY2",
            normalized_x=0.9,
            normalized_y=0.5,
            position=Point(3000, 500),
            edge=DockEdge.RIGHT,
        )
        primary = Monitor("DISPLAY1", Rect(0, 0, 1920, 1040), primary=True)

        recovered = recover_to_monitors(saved, Size(56, 56), [primary])

        self.assertEqual(recovered.monitor_name, "DISPLAY1")
        self.assertEqual(recovered.edge, DockEdge.RIGHT)
        self.assertEqual(recovered.position.x, 1864)
        self.assertGreaterEqual(recovered.position.y, 0)
        self.assertLessEqual(recovered.position.y, 984)

    def test_existing_monitor_uses_saved_normalized_coordinates(self) -> None:
        saved = OverlayPlacement(
            monitor_name="DISPLAY2",
            normalized_x=0.5,
            normalized_y=0.25,
            position=Point(0, 0),
            edge=None,
        )
        monitor = Monitor("DISPLAY2", Rect(1920, 0, 2560, 1440), primary=False)

        recovered = recover_to_monitors(saved, Size(56, 56), [monitor])

        self.assertEqual(recovered.position, Point(3172, 346))


if __name__ == "__main__":
    unittest.main()
