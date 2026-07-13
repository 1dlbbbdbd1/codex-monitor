from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .file_locations import COMPANION_SETTINGS_FILE
from .overlay_geometry import DockEdge, OverlayPlacement, Point


@dataclass(frozen=True, slots=True)
class OverlaySettings:
    placement: OverlayPlacement | None = None
    overlay_enabled: bool = True
    auto_hide: bool = True
    always_on_top: bool = True


def overlay_settings_with_visibility(settings: OverlaySettings, visible: bool) -> OverlaySettings:
    return OverlaySettings(
        placement=settings.placement,
        overlay_enabled=visible,
        auto_hide=settings.auto_hide,
        always_on_top=settings.always_on_top,
    )


def overlay_settings_with_topmost(settings: OverlaySettings, always_on_top: bool) -> OverlaySettings:
    return OverlaySettings(
        placement=settings.placement,
        overlay_enabled=settings.overlay_enabled,
        auto_hide=settings.auto_hide,
        always_on_top=always_on_top,
    )


class OverlaySettingsStore:
    def __init__(self, path: Path = COMPANION_SETTINGS_FILE) -> None:
        self.path = path

    def load(self) -> OverlaySettings:
        if not self.path.exists():
            return OverlaySettings()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("version") != 1:
                return OverlaySettings()
            placement_payload = payload.get("placement")
            placement = self._placement_from_dict(placement_payload) if isinstance(placement_payload, dict) else None
            return OverlaySettings(
                placement=placement,
                overlay_enabled=bool(payload.get("overlayEnabled", True)),
                auto_hide=bool(payload.get("autoHide", True)),
                always_on_top=bool(payload.get("alwaysOnTop", True)),
            )
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return OverlaySettings()

    def save(self, settings: OverlaySettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "placement": self._placement_to_dict(settings.placement) if settings.placement else None,
            "overlayEnabled": settings.overlay_enabled,
            "autoHide": settings.auto_hide,
            "alwaysOnTop": settings.always_on_top,
        }
        temporary = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)

    @staticmethod
    def _placement_to_dict(placement: OverlayPlacement) -> dict[str, Any]:
        return {
            "monitorName": placement.monitor_name,
            "normalizedX": placement.normalized_x,
            "normalizedY": placement.normalized_y,
            "x": placement.position.x,
            "y": placement.position.y,
            "edge": placement.edge.value if placement.edge else None,
        }

    @staticmethod
    def _placement_from_dict(payload: dict[str, Any]) -> OverlayPlacement:
        edge_value = payload.get("edge")
        return OverlayPlacement(
            monitor_name=str(payload["monitorName"]),
            normalized_x=float(payload["normalizedX"]),
            normalized_y=float(payload["normalizedY"]),
            position=Point(int(payload["x"]), int(payload["y"])),
            edge=DockEdge(str(edge_value)) if edge_value else None,
        )
