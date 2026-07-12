from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class DockEdge(str, Enum):
    LEFT = "left"
    RIGHT = "right"


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Size:
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True, slots=True)
class Monitor:
    name: str
    work_area: Rect
    primary: bool = False


@dataclass(frozen=True, slots=True)
class OverlayPlacement:
    monitor_name: str
    normalized_x: float
    normalized_y: float
    position: Point
    edge: DockEdge | None


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return min(max(value, minimum), maximum)


def _normalized(value: int, start: int, span: int) -> float:
    if span <= 0:
        return 0.0
    return min(max((value - start) / span, 0.0), 1.0)


def dock_target(
    work_area: Rect,
    ball_size: Size,
    release: Point,
    *,
    monitor_name: str,
    threshold_px: int = 24,
) -> OverlayPlacement:
    maximum_x = max(work_area.x, work_area.right - ball_size.width)
    maximum_y = max(work_area.y, work_area.bottom - ball_size.height)
    y = _clamp(release.y, work_area.y, maximum_y)

    edge: DockEdge | None = None
    if release.x - work_area.x <= threshold_px:
        edge = DockEdge.LEFT
        x = work_area.x
    elif work_area.right - release.x <= threshold_px:
        edge = DockEdge.RIGHT
        x = maximum_x
    else:
        x = _clamp(release.x, work_area.x, maximum_x)

    return OverlayPlacement(
        monitor_name=monitor_name,
        normalized_x=_normalized(x, work_area.x, maximum_x - work_area.x),
        normalized_y=_normalized(y, work_area.y, maximum_y - work_area.y),
        position=Point(x, y),
        edge=edge,
    )


def hidden_target(
    work_area: Rect,
    ball_size: Size,
    edge: DockEdge,
    *,
    y: int,
    handle_px: int = 12,
) -> Point:
    visible_handle = min(max(handle_px, 1), ball_size.width)
    if edge is DockEdge.LEFT:
        x = work_area.x - ball_size.width + visible_handle
    else:
        x = work_area.right - visible_handle
    maximum_y = max(work_area.y, work_area.bottom - ball_size.height)
    return Point(x, _clamp(y, work_area.y, maximum_y))


def recover_to_monitors(
    saved: OverlayPlacement,
    ball_size: Size,
    monitors: Iterable[Monitor],
) -> OverlayPlacement:
    available = list(monitors)
    if not available:
        return saved
    monitor = next((candidate for candidate in available if candidate.name == saved.monitor_name), None)
    if monitor is None:
        monitor = next((candidate for candidate in available if candidate.primary), available[0])

    work = monitor.work_area
    x_span = max(0, work.width - ball_size.width)
    y_span = max(0, work.height - ball_size.height)
    y = work.y + round(min(max(saved.normalized_y, 0.0), 1.0) * y_span)
    if saved.edge is DockEdge.LEFT:
        x = work.x
    elif saved.edge is DockEdge.RIGHT:
        x = work.x + x_span
    else:
        x = work.x + round(min(max(saved.normalized_x, 0.0), 1.0) * x_span)

    return OverlayPlacement(
        monitor_name=monitor.name,
        normalized_x=_normalized(x, work.x, x_span),
        normalized_y=_normalized(y, work.y, y_span),
        position=Point(x, y),
        edge=saved.edge,
    )
