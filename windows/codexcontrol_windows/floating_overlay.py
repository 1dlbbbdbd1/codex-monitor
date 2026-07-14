from __future__ import annotations

import ctypes
import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from PIL import ImageTk

from .activity_models import ActivityStatus, AggregateStatus, TaskProjection
from .brand_icon import build_quota_dial_icon
from .notification_state import BadgeState
from .overlay_geometry import DockEdge, Monitor, Point, Rect, Size, dock_target, hidden_target, recover_to_monitors
from .settings_store import OverlaySettings, OverlaySettingsStore, overlay_settings_with_quota_mode
from .ui_theme import CODEX_DARK_PALETTE


BALL_SIZE = 56
PANEL_WIDTH = 340
PANEL_HEIGHT = 430
TRANSPARENT_KEY = "#010203"


@dataclass(frozen=True, slots=True)
class QuotaRow:
    label: str
    remaining_percent: float
    reset_text: str
    mode: str = ""

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
    activity_stale: bool
    quota_mode: str
    quota_percent: float | None
    quota_percent_text: str
    quota_label: str
    available_quota_modes: tuple[str, ...]


_STATUS_TEXT = {
    ActivityStatus.UNKNOWN: "状态未知",
    ActivityStatus.IDLE: "空闲",
    ActivityStatus.WORKING: "工作中",
    ActivityStatus.WAITING_APPROVAL: "等待审批",
    ActivityStatus.COMPLETED: "已完成",
    ActivityStatus.FAILED: "执行失败",
}

_STATUS_COLOR = {
    ActivityStatus.UNKNOWN: CODEX_DARK_PALETTE["neutral"],
    ActivityStatus.IDLE: CODEX_DARK_PALETTE["neutral"],
    ActivityStatus.WORKING: CODEX_DARK_PALETTE["success"],
    ActivityStatus.WAITING_APPROVAL: CODEX_DARK_PALETTE["warning"],
    ActivityStatus.COMPLETED: CODEX_DARK_PALETTE["info"],
    ActivityStatus.FAILED: CODEX_DARK_PALETTE["danger"],
}


def build_overlay_view_model(
    *,
    aggregate: AggregateStatus,
    badge: BadgeState,
    quota_rows: Sequence[QuotaRow],
    quota_mode: str = "5h",
    tasks: Iterable[TaskProjection],
    health_text: str,
    activity_stale: bool = False,
) -> OverlayViewModel:
    rows = tuple(quota_rows)
    selected_quota = next((row for row in rows if row.mode == quota_mode), rows[0] if rows else None)
    selected_mode = selected_quota.mode if selected_quota else quota_mode
    task_rows = () if activity_stale else tuple(
        TaskRow(
            thread_id=task.thread_id,
            title=_task_title(task),
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
        badge_color=CODEX_DARK_PALETTE["danger"] if urgent_badge else CODEX_DARK_PALETTE["info"],
        keep_handle_visible=badge.visible,
        quota_rows=rows,
        task_rows=task_rows,
        health_text=health_text,
        activity_stale=activity_stale,
        quota_mode=selected_mode,
        quota_percent=selected_quota.remaining_percent if selected_quota else None,
        quota_percent_text=selected_quota.remaining_text if selected_quota else "--",
        quota_label={"5h": "5小时", "7d": "7天"}.get(selected_mode, selected_mode or "额度"),
        available_quota_modes=tuple(row.mode for row in rows if row.mode in {"5h", "7d"}),
    )


def _task_title(task: TaskProjection) -> str:
    if task.task_title:
        return task.task_title
    if task.project_name:
        return f"{task.project_name} · 任务 {task.thread_id[-4:].upper()}"
    return "Codex 任务"


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
        on_hide_requested: Callable[[], None] | None = None,
        on_repair_requested: Callable[[], None] | None = None,
        on_quota_mode_changed: Callable[[str], None] | None = None,
    ) -> None:
        self.parent = parent
        self.settings_store = settings_store or OverlaySettingsStore()
        self.settings = self.settings_store.load()
        self.on_refresh = on_refresh or (lambda: None)
        self.on_task_open = on_task_open or (lambda _thread_id: None)
        self.on_panel_viewed = on_panel_viewed or (lambda: None)
        self.on_hide_requested = on_hide_requested or self.hide
        self.on_repair_requested = on_repair_requested or (lambda: None)
        self.on_quota_mode_changed = on_quota_mode_changed or (lambda _mode: None)
        self.model = build_overlay_view_model(
            aggregate=AggregateStatus(ActivityStatus.IDLE, 0, 0),
            badge=BadgeState(),
            quota_rows=(),
            tasks=(),
            health_text="等待 Codex 事件",
            activity_stale=False,
        )

        self.window = tk.Toplevel(parent)
        self.window.title("Codex 悬浮球")
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", self.settings.always_on_top)
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
        self.canvas.bind("<Button-3>", lambda _event: self.on_hide_requested())
        self._render_ball()

    def show(self) -> None:
        self.window.attributes("-topmost", self.settings.always_on_top)
        self.window.geometry(f"{BALL_SIZE}x{BALL_SIZE}+{self._placement.position.x}+{self._placement.position.y}")
        self.window.deiconify()
        self.window.lift()
        self._schedule_hide()

    def set_always_on_top(self, always_on_top: bool) -> None:
        self.settings = OverlaySettings(
            placement=self.settings.placement,
            overlay_enabled=self.settings.overlay_enabled,
            auto_hide=self.settings.auto_hide,
            always_on_top=always_on_top,
            quota_mode=self.settings.quota_mode,
        )
        try:
            self.window.attributes("-topmost", always_on_top)
            if self._panel is not None and self._panel.winfo_exists():
                self._panel.attributes("-topmost", always_on_top)
        except tk.TclError:
            pass

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
        if model == self.model:
            return
        self.model = model
        hidden_edge = None
        if (
            self.window.state() == "normal"
            and self._placement.edge is not None
            and self.window.winfo_x() != self._placement.position.x
        ):
            hidden_edge = self._placement.edge
        self._render_ball(hidden_edge)
        if self._panel is not None and self._panel.winfo_exists():
            self._render_panel()

    def toggle_panel(self) -> None:
        if self._panel is not None and self._panel.winfo_exists():
            self._close_panel()
            return
        self._cancel_hide()
        self._reveal()
        self._panel = tk.Toplevel(self.parent)
        self._panel.title("Codex 状态面板")
        self._panel.overrideredirect(True)
        self._panel.attributes("-topmost", self.settings.always_on_top)
        self._panel.configure(bg=CODEX_DARK_PALETTE["shell"])
        self._panel.bind("<Escape>", lambda _event: self._close_panel())
        self._position_panel()
        self._render_panel()
        self.on_panel_viewed()

    def _render_ball(self, hidden_edge: DockEdge | None = None) -> None:
        self.canvas.delete("all")
        quota_color = self._quota_color(self.model.quota_percent) if self.model.quota_percent is not None else CODEX_DARK_PALETTE["neutral"]
        image = build_quota_dial_icon(
            BALL_SIZE,
            remaining_percent=self.model.quota_percent or 0,
            accent=quota_color,
            fill=CODEX_DARK_PALETTE["shell"],
            track=CODEX_DARK_PALETTE["track"],
            border=CODEX_DARK_PALETTE["hairline"],
        )
        self._icon = ImageTk.PhotoImage(image)
        self.canvas.create_image(BALL_SIZE // 2, BALL_SIZE // 2, image=self._icon)
        self.canvas.create_text(
            BALL_SIZE // 2,
            BALL_SIZE // 2 - 3,
            text=self.model.quota_percent_text,
            fill=CODEX_DARK_PALETTE["text"],
            font=("Segoe UI Semibold", 11, "bold"),
        )
        self.canvas.create_text(
            BALL_SIZE // 2,
            BALL_SIZE // 2 + 10,
            text=self.model.quota_label,
            fill=CODEX_DARK_PALETTE["muted"],
            font=("Microsoft YaHei UI", 6, "bold"),
        )
        if self.model.badge_visible:
            if hidden_edge is DockEdge.RIGHT:
                bounds = (1, 21, 13, 33)
            elif hidden_edge is DockEdge.LEFT:
                bounds = (43, 21, 55, 33)
            else:
                bounds = (40, 3, 54, 17)
            self.canvas.create_oval(*bounds, fill=self.model.badge_color, outline="#ffffff", width=2)
        else:
            self.canvas.create_oval(44, 5, 50, 11, fill=self.model.accent_color, outline=CODEX_DARK_PALETTE["shell"], width=1)

    def _render_panel(self) -> None:
        assert self._panel is not None
        for child in self._panel.winfo_children():
            child.destroy()
        panel = tk.Frame(self._panel, bg=CODEX_DARK_PALETTE["shell"], padx=18, pady=16)
        panel.pack(fill="both", expand=True)

        header = tk.Frame(panel, bg=CODEX_DARK_PALETTE["shell"])
        header.pack(fill="x")
        tk.Label(
            header,
            text=self.model.status_text,
            fg=self.model.accent_color,
            bg=CODEX_DARK_PALETTE["shell"],
            font=("Microsoft YaHei UI", 15, "bold"),
        ).pack(side="left")
        tk.Button(
            header,
            text="刷新",
            command=self.on_refresh,
            fg=CODEX_DARK_PALETTE["text"],
            bg=CODEX_DARK_PALETTE["panel_alt"],
            activebackground=CODEX_DARK_PALETTE["accent_soft"],
            activeforeground="#ffffff",
            relief="flat",
            padx=10,
        ).pack(side="right")
        tk.Label(panel, text=self.model.health_text, fg=CODEX_DARK_PALETTE["muted"], bg=CODEX_DARK_PALETTE["shell"], anchor="w", font=("Microsoft YaHei UI", 10)).pack(fill="x", pady=(2, 14))
        if self.model.activity_stale:
            tk.Button(
                panel,
                text="修复状态连接",
                command=self.on_repair_requested,
                fg="#ffffff",
                bg=CODEX_DARK_PALETTE["accent_line"],
                activebackground=CODEX_DARK_PALETTE["accent"],
                activeforeground="#ffffff",
                relief="flat",
                padx=10,
                pady=4,
            ).pack(fill="x", pady=(0, 12))

        quota_header = tk.Frame(panel, bg=CODEX_DARK_PALETTE["shell"])
        quota_header.pack(fill="x", pady=(0, 5))
        tk.Label(quota_header, text="额度与刷新时间", fg=CODEX_DARK_PALETTE["muted"], bg=CODEX_DARK_PALETTE["shell"], font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        for mode, label in (("5h", "5小时"), ("7d", "7天")):
            available = mode in self.model.available_quota_modes
            selected = mode == self.model.quota_mode
            tk.Button(
                quota_header,
                text=label,
                command=lambda value=mode: self._set_quota_mode(value),
                state="normal" if available else "disabled",
                fg="#ffffff" if selected else CODEX_DARK_PALETTE["muted"],
                disabledforeground=CODEX_DARK_PALETTE["subtle"],
                bg=CODEX_DARK_PALETTE["accent_line"] if selected else CODEX_DARK_PALETTE["panel_alt"],
                activebackground=CODEX_DARK_PALETTE["accent"],
                activeforeground="#ffffff",
                relief="flat",
                padx=7,
                pady=2,
                font=("Microsoft YaHei UI", 8, "bold"),
            ).pack(side="right", padx=(4, 0))
        if self.model.quota_rows:
            for quota in self.model.quota_rows:
                row = tk.Frame(panel, bg=CODEX_DARK_PALETTE["panel"], padx=10, pady=7)
                row.pack(fill="x", pady=2)
                tk.Label(row, text=quota.label, fg=CODEX_DARK_PALETTE["text"], bg=CODEX_DARK_PALETTE["panel"], font=("Microsoft YaHei UI", 10)).pack(side="left")
                tk.Label(row, text=quota.reset_text, fg=CODEX_DARK_PALETTE["subtle"], bg=CODEX_DARK_PALETTE["panel"], font=("Microsoft YaHei UI", 9)).pack(side="right", padx=(8, 0))
                tk.Label(row, text=quota.remaining_text, fg=self._quota_color(quota.remaining_percent), bg=CODEX_DARK_PALETTE["panel"], font=("Segoe UI", 10, "bold")).pack(side="right")
        else:
            self._empty_row(panel, "尚无额度数据")

        self._section_title(panel, "最近任务", top=14)
        if self.model.task_rows:
            for task in self.model.task_rows:
                row = tk.Frame(panel, bg=CODEX_DARK_PALETTE["panel"], padx=10, pady=7, cursor="hand2")
                row.pack(fill="x", pady=2)
                title = tk.Label(row, text=task.title, fg=CODEX_DARK_PALETTE["text"], bg=CODEX_DARK_PALETTE["panel"], anchor="w", font=("Microsoft YaHei UI", 10, "bold"))
                title.pack(fill="x")
                detail = tk.Label(row, text=f"{task.status_text} · {task.project}", fg=_STATUS_COLOR[task.status], bg=CODEX_DARK_PALETTE["panel"], anchor="w", font=("Microsoft YaHei UI", 9))
                detail.pack(fill="x")
                for widget in (row, title, detail):
                    widget.bind("<Button-1>", lambda _event, thread_id=task.thread_id: self.on_task_open(thread_id))
        else:
            self._empty_row(panel, "等待 Codex 活动")

        tk.Label(
            panel,
            text="单击悬浮球收起 · 右键隐藏",
            fg=CODEX_DARK_PALETTE["subtle"],
            bg=CODEX_DARK_PALETTE["shell"],
            font=("Microsoft YaHei UI", 9),
        ).pack(side="bottom", pady=(12, 0))

    @staticmethod
    def _section_title(parent: tk.Misc, text: str, *, top: int = 0) -> None:
        tk.Label(parent, text=text, fg=CODEX_DARK_PALETTE["muted"], bg=CODEX_DARK_PALETTE["shell"], anchor="w", font=("Microsoft YaHei UI", 10, "bold")).pack(fill="x", pady=(top, 5))

    @staticmethod
    def _empty_row(parent: tk.Misc, text: str) -> None:
        tk.Label(parent, text=text, fg=CODEX_DARK_PALETTE["muted"], bg=CODEX_DARK_PALETTE["panel"], padx=10, pady=9, anchor="w", font=("Microsoft YaHei UI", 10)).pack(fill="x")

    @staticmethod
    def _quota_color(remaining: float) -> str:
        if remaining <= 10:
            return CODEX_DARK_PALETTE["danger"]
        if remaining <= 20:
            return CODEX_DARK_PALETTE["warning"]
        return CODEX_DARK_PALETTE["accent"]

    def _set_quota_mode(self, quota_mode: str) -> None:
        if quota_mode not in self.model.available_quota_modes:
            return
        self.settings = overlay_settings_with_quota_mode(self.settings, quota_mode)
        try:
            self.settings_store.save(self.settings)
        except OSError:
            pass
        self.on_quota_mode_changed(quota_mode)

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
        self._render_ball()

    def _schedule_hide(self) -> None:
        self._cancel_hide()
        if not self.settings.auto_hide or self._placement.edge is None or self._panel is not None:
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
        self._render_ball(self._placement.edge)
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
            always_on_top=self.settings.always_on_top,
            quota_mode=self.settings.quota_mode,
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
