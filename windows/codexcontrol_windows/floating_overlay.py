from __future__ import annotations

import ctypes
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from PIL import ImageTk

from .activity_models import ActivityStatus, AggregateStatus, TaskProjection
from .brand_icon import build_orbit_dial_icon
from .notification_state import BadgeState
from .overlay_geometry import DockEdge, Monitor, Point, Rect, Size, dock_target, hidden_target, recover_to_monitors
from .settings_store import OverlaySettings, OverlaySettingsStore


BALL_SIZE = 56
PANEL_WIDTH = 340
PANEL_HEIGHT = 430
TRANSPARENT_KEY = "#010203"


@dataclass(frozen=True, slots=True)
class QuotaRow:
    label: str
    remaining_percent: float
    reset_text: str

    @property
    def remaining_text(self) -> str:
        return f"{self.remaining_percent:.0f}%"


@dataclass(frozen=True, slots=True)
class TaskRow:
    thread_id: str
    title: str
    project: str
    status: ActivityStatus
    status_text: str


@dataclass(frozen=True, slots=True)
class OverlayViewModel:
    status: ActivityStatus
    status_text: str
    accent_color: str
    count_text: str
    badge_visible: bool
    badge_color: str
    keep_handle_visible: bool
    quota_rows: tuple[QuotaRow, ...]
    task_rows: tuple[TaskRow, ...]
    health_text: str


_STATUS_TEXT = {
    ActivityStatus.UNKNOWN: "状态未知",
    ActivityStatus.IDLE: "空闲",
    ActivityStatus.WORKING: "工作中",
    ActivityStatus.WAITING_APPROVAL: "等待审批",
    ActivityStatus.COMPLETED: "已完成",
    ActivityStatus.FAILED: "执行失败",
}

_STATUS_COLOR = {
    ActivityStatus.UNKNOWN: "#94a3b8",
    ActivityStatus.IDLE: "#94a3b8",
    ActivityStatus.WORKING: "#3ad06d",
    ActivityStatus.WAITING_APPROVAL: "#f59e0b",
    ActivityStatus.COMPLETED: "#38bdf8",
    ActivityStatus.FAILED: "#ef4444",
}


def build_overlay_view_model(
    *,
    aggregate: AggregateStatus,
    badge: BadgeState,
    quota_rows: Sequence[QuotaRow],
    tasks: Iterable[TaskProjection],
    health_text: str,
) -> OverlayViewModel:
    task_rows = tuple(
        TaskRow(
            thread_id=task.thread_id,
            title=task.task_title or task.project_name or "Codex 任务",
            project=task.project_name or "未命名项目",
            status=task.status,
            status_text=_STATUS_TEXT[task.status],
        )
        for task in sorted(tasks, key=lambda item: item.updated_at, reverse=True)[:5]
    )
    urgent_badge = badge.approval or badge.failure
    count = aggregate.attention_count if aggregate.attention_count else aggregate.working_count
    return OverlayViewModel(
        status=aggregate.status,
        status_text=_STATUS_TEXT[aggregate.status],
        accent_color=_STATUS_COLOR[aggregate.status],
        count_text=str(count) if count else "",
        badge_visible=badge.visible,
        badge_color="#ef4444" if urgent_badge else "#38bdf8",
        keep_handle_visible=badge.approval,
        quota_rows=tuple(quota_rows),
        task_rows=task_rows,
        health_text=health_text,
    )


class FloatingOverlay:
    """Small topmost companion window; business state is supplied as a view model."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        settings_store: OverlaySettingsStore | None = None,
        on_refresh: Callable[[], None] | None = None,
        on_task_open: Callable[[str], None] | None = None,
        on_panel_viewed: Callable[[], None] | None = None,
    ) -> None:
        self.parent = parent
        self.settings_store = settings_store or OverlaySettingsStore()
        self.settings = self.settings_store.load()
        self.on_refresh = on_refresh or (lambda: None)
        self.on_task_open = on_task_open or (lambda _thread_id: None)
        self.on_panel_viewed = on_panel_viewed or (lambda: None)
        self.model = build_overlay_view_model(
            aggregate=AggregateStatus(ActivityStatus.IDLE, 0, 0),
            badge=BadgeState(),
            quota_rows=(),
            tasks=(),
            health_text="等待 Codex 事件",
        )

        self.window = tk.Toplevel(parent)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg=TRANSPARENT_KEY)
        try:
            self.window.wm_attributes("-transparentcolor", TRANSPARENT_KEY)
        except tk.TclError:
            pass
        self.canvas = tk.Canvas(
            self.window,
            width=BALL_SIZE,
            height=BALL_SIZE,
            bg=TRANSPARENT_KEY,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self._icon: ImageTk.PhotoImage | None = None
        self._panel: tk.Toplevel | None = None
        self._drag_origin: tuple[int, int, int, int] | None = None
        self._dragged = False
        self._hide_job: str | None = None
        self._placement = self._initial_placement()

        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.canvas.bind("<Enter>", self._reveal)
        self.canvas.bind("<Leave>", lambda _event: self._schedule_hide())
        self.canvas.bind("<Button-3>", lambda _event: self.hide())
        self._render_ball()

    def show(self) -> None:
        self.window.geometry(f"{BALL_SIZE}x{BALL_SIZE}+{self._placement.position.x}+{self._placement.position.y}")
        self.window.deiconify()
        self.window.lift()
        self._schedule_hide()

    def hide(self) -> None:
        self._cancel_hide()
        self._close_panel()
        self.window.withdraw()

    def destroy(self) -> None:
        self._cancel_hide()
        self._close_panel()
        if self.window.winfo_exists():
            self.window.destroy()

    def update(self, model: OverlayViewModel) -> None:
        self.model = model
        self._render_ball()
        if model.keep_handle_visible:
            self._reveal()
        if self._panel is not None and self._panel.winfo_exists():
            self._render_panel()

    def toggle_panel(self) -> None:
        if self._panel is not None and self._panel.winfo_exists():
            self._close_panel()
            return
        self._cancel_hide()
        self._reveal()
        self._panel = tk.Toplevel(self.parent)
        self._panel.overrideredirect(True)
        self._panel.attributes("-topmost", True)
        self._panel.configure(bg="#111820")
        self._panel.bind("<Escape>", lambda _event: self._close_panel())
        self._position_panel()
        self._render_panel()
        self.on_panel_viewed()

    def _render_ball(self) -> None:
        self.canvas.delete("all")
        image = build_orbit_dial_icon(BALL_SIZE, accent=self.model.accent_color)
        self._icon = ImageTk.PhotoImage(image)
        self.canvas.create_image(BALL_SIZE // 2, BALL_SIZE // 2, image=self._icon)
        if self.model.count_text:
            self.canvas.create_text(
                BALL_SIZE // 2,
                BALL_SIZE // 2 + 1,
                text=self.model.count_text,
                fill="#ffffff",
                font=("Segoe UI Semibold", 10),
            )
        if self.model.badge_visible:
            self.canvas.create_oval(40, 3, 54, 17, fill=self.model.badge_color, outline="#ffffff", width=2)

    def _render_panel(self) -> None:
        assert self._panel is not None
        for child in self._panel.winfo_children():
            child.destroy()
        panel = tk.Frame(self._panel, bg="#111820", padx=18, pady=16)
        panel.pack(fill="both", expand=True)

        header = tk.Frame(panel, bg="#111820")
        header.pack(fill="x")
        tk.Label(
            header,
            text=self.model.status_text,
            fg=self.model.accent_color,
            bg="#111820",
            font=("Microsoft YaHei UI", 14, "bold"),
        ).pack(side="left")
        tk.Button(
            header,
            text="刷新",
            command=self.on_refresh,
            fg="#dbeafe",
            bg="#1e293b",
            activebackground="#334155",
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
        ).pack(side="right")
        tk.Label(panel, text=self.model.health_text, fg="#94a3b8", bg="#111820", anchor="w").pack(fill="x", pady=(2, 14))

        self._section_title(panel, "额度与刷新时间")
        if self.model.quota_rows:
            for quota in self.model.quota_rows:
                row = tk.Frame(panel, bg="#17212b", padx=10, pady=7)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=quota.label, fg="#cbd5e1", bg="#17212b").pack(side="left")
                tk.Label(row, text=quota.reset_text, fg="#64748b", bg="#17212b").pack(side="right", padx=(8, 0))
                tk.Label(row, text=quota.remaining_text, fg=self._quota_color(quota.remaining_percent), bg="#17212b", font=("Segoe UI", 10, "bold")).pack(side="right")
        else:
            self._empty_row(panel, "尚无额度数据")

        self._section_title(panel, "最近任务", top=14)
        if self.model.task_rows:
            for task in self.model.task_rows:
                row = tk.Frame(panel, bg="#17212b", padx=10, pady=7, cursor="hand2")
                row.pack(fill="x", pady=2)
                title = tk.Label(row, text=task.title, fg="#e2e8f0", bg="#17212b", anchor="w")
                title.pack(fill="x")
                detail = tk.Label(row, text=f"{task.status_text} · {task.project}", fg=_STATUS_COLOR[task.status], bg="#17212b", anchor="w", font=("Segoe UI", 8))
                detail.pack(fill="x")
                for widget in (row, title, detail):
                    widget.bind("<Button-1>", lambda _event, thread_id=task.thread_id: self.on_task_open(thread_id))
        else:
            self._empty_row(panel, "等待 Codex 活动")

        tk.Label(
            panel,
            text="单击悬浮球收起 · 右键隐藏",
            fg="#526170",
            bg="#111820",
            font=("Segoe UI", 8),
        ).pack(side="bottom", pady=(12, 0))

    @staticmethod
    def _section_title(parent: tk.Misc, text: str, *, top: int = 0) -> None:
        tk.Label(parent, text=text, fg="#94a3b8", bg="#111820", anchor="w", font=("Microsoft YaHei UI", 9, "bold")).pack(fill="x", pady=(top, 5))

    @staticmethod
    def _empty_row(parent: tk.Misc, text: str) -> None:
        tk.Label(parent, text=text, fg="#64748b", bg="#17212b", padx=10, pady=9, anchor="w").pack(fill="x")

    @staticmethod
    def _quota_color(remaining: float) -> str:
        if remaining <= 10:
            return "#ef4444"
        if remaining <= 20:
            return "#f59e0b"
        return "#3ad06d"

    def _press(self, event: tk.Event) -> None:
        self._cancel_hide()
        self._dragged = False
        self._drag_origin = (event.x_root, event.y_root, self.window.winfo_x(), self.window.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        if self._drag_origin is None:
            return
        start_x, start_y, window_x, window_y = self._drag_origin
        dx, dy = event.x_root - start_x, event.y_root - start_y
        self._dragged = self._dragged or abs(dx) + abs(dy) > 4
        self.window.geometry(f"+{window_x + dx}+{window_y + dy}")
        if self._panel is not None:
            self._position_panel()

    def _release(self, event: tk.Event) -> None:
        self._drag_origin = None
        if not self._dragged:
            self.toggle_panel()
            return
        monitor = self._current_monitor(event.x_root, event.y_root)
        self._placement = dock_target(
            monitor.work_area,
            Size(BALL_SIZE, BALL_SIZE),
            Point(self.window.winfo_x(), self.window.winfo_y()),
            monitor_name=monitor.name,
        )
        self.window.geometry(f"+{self._placement.position.x}+{self._placement.position.y}")
        self._save_settings()
        self._schedule_hide()

    def _reveal(self, _event: tk.Event | None = None) -> None:
        self._cancel_hide()
        point = self._placement.position
        self.window.geometry(f"+{point.x}+{point.y}")

    def _schedule_hide(self) -> None:
        self._cancel_hide()
        if not self.settings.auto_hide or self._placement.edge is None or self.model.keep_handle_visible or self._panel is not None:
            return
        self._hide_job = self.window.after(2000, self._hide_to_edge)

    def _cancel_hide(self) -> None:
        if self._hide_job is not None:
            try:
                self.window.after_cancel(self._hide_job)
            except tk.TclError:
                pass
            self._hide_job = None

    def _hide_to_edge(self) -> None:
        self._hide_job = None
        if self._placement.edge is None:
            return
        monitor = next((item for item in _enumerate_monitors(self.parent) if item.name == self._placement.monitor_name), self._current_monitor(self._placement.position.x, self._placement.position.y))
        target = hidden_target(monitor.work_area, Size(BALL_SIZE, BALL_SIZE), self._placement.edge, y=self._placement.position.y)
        self.window.geometry(f"+{target.x}+{target.y}")

    def _position_panel(self) -> None:
        if self._panel is None:
            return
        monitor = self._current_monitor(self.window.winfo_x(), self.window.winfo_y())
        work = monitor.work_area
        ball_x, ball_y = self.window.winfo_x(), self.window.winfo_y()
        if ball_x + BALL_SIZE + PANEL_WIDTH + 12 <= work.right:
            x = ball_x + BALL_SIZE + 10
        else:
            x = ball_x - PANEL_WIDTH - 10
        y = min(max(ball_y, work.y), max(work.y, work.bottom - PANEL_HEIGHT))
        self._panel.geometry(f"{PANEL_WIDTH}x{PANEL_HEIGHT}+{x}+{y}")

    def _close_panel(self) -> None:
        if self._panel is not None:
            try:
                self._panel.destroy()
            except tk.TclError:
                pass
            self._panel = None
        self._schedule_hide()

    def _initial_placement(self):
        monitors = _enumerate_monitors(self.parent)
        saved = self.settings.placement
        if saved is not None:
            return recover_to_monitors(saved, Size(BALL_SIZE, BALL_SIZE), monitors)
        primary = next((monitor for monitor in monitors if monitor.primary), monitors[0])
        return dock_target(
            primary.work_area,
            Size(BALL_SIZE, BALL_SIZE),
            Point(primary.work_area.right, primary.work_area.y + primary.work_area.height // 3),
            monitor_name=primary.name,
        )

    def _current_monitor(self, x: int, y: int) -> Monitor:
        monitors = _enumerate_monitors(self.parent)
        return next(
            (monitor for monitor in monitors if monitor.work_area.x <= x < monitor.work_area.right and monitor.work_area.y <= y < monitor.work_area.bottom),
            next((monitor for monitor in monitors if monitor.primary), monitors[0]),
        )

    def _save_settings(self) -> None:
        self.settings = OverlaySettings(
            placement=self._placement,
            overlay_enabled=self.settings.overlay_enabled,
            auto_hide=self.settings.auto_hide,
        )
        try:
            self.settings_store.save(self.settings)
        except OSError:
            pass


def _enumerate_monitors(parent: tk.Misc) -> list[Monitor]:
    """Return Win32 work areas, with a Tk-safe single-monitor fallback."""
    try:
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        monitors: list[Monitor] = []
        monitor_info_primary = 1

        class MONITORINFOEXW(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
                ("szDevice", wintypes.WCHAR * 32),
            ]

        callback_type = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(wintypes.RECT), wintypes.LPARAM)

        def callback(handle, _hdc, _rect, _data):
            info = MONITORINFOEXW()
            info.cbSize = ctypes.sizeof(info)
            if user32.GetMonitorInfoW(handle, ctypes.byref(info)):
                work = info.rcWork
                monitors.append(
                    Monitor(
                        name=info.szDevice,
                        work_area=Rect(work.left, work.top, work.right - work.left, work.bottom - work.top),
                        primary=bool(info.dwFlags & monitor_info_primary),
                    )
                )
            return 1

        user32.EnumDisplayMonitors(0, 0, callback_type(callback), 0)
        if monitors:
            return monitors
    except (AttributeError, OSError, TypeError):
        pass
    return [Monitor("primary", Rect(0, 0, parent.winfo_screenwidth(), parent.winfo_screenheight()), primary=True)]
