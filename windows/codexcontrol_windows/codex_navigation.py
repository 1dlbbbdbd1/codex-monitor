from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .activity_models import TaskProjection


class NavigationMode(str, Enum):
    PRECISE = "precise"
    FOREGROUND_FALLBACK = "foregroundFallback"


@dataclass(frozen=True, slots=True)
class NavigationResult:
    mode: NavigationMode
    succeeded: bool


class CodexNavigator:
    def __init__(self, *, foreground: Callable[[], bool] | None = None) -> None:
        self._foreground = foreground or foreground_codex_window

    def open_task(
        self,
        task: TaskProjection,
        *,
        precise_handler: Callable[[TaskProjection], bool] | None = None,
    ) -> NavigationResult:
        if precise_handler is not None:
            try:
                if precise_handler(task):
                    return NavigationResult(NavigationMode.PRECISE, True)
            except Exception:
                pass
        return NavigationResult(NavigationMode.FOREGROUND_FALLBACK, self._foreground())


def foreground_codex_window() -> bool:
    """Bring an existing Codex window forward without reading or editing private app state."""
    if os.name != "nt":
        return False
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found: list[int] = []
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

        def callback(hwnd: int, _lparam: int) -> bool:
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.casefold()
            if title == "codex" or title.startswith("codex ") or title.endswith(" - codex"):
                found.append(hwnd)
                return False
            return True

        user32.EnumWindows(callback_type(callback), 0)
        if not found:
            return False
        hwnd = found[0]
        user32.ShowWindow(hwnd, 9)
        return bool(user32.SetForegroundWindow(hwnd))
    except (AttributeError, OSError, TypeError):
        return False
