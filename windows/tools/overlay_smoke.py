from __future__ import annotations

import argparse
import tkinter as tk
from datetime import datetime, timezone

from codexcontrol_windows.activity_models import ActivityStatus, AggregateStatus, TaskProjection
from codexcontrol_windows.floating_overlay import FloatingOverlay, QuotaRow, build_overlay_view_model
from codexcontrol_windows.notification_state import BadgeState


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=5.0)
    args = parser.parse_args()

    root = tk.Tk()
    root.withdraw()
    overlay = FloatingOverlay(root)
    task = TaskProjection("demo", "turn-1", "验证悬浮球 Demo", "demo", None, ActivityStatus.WORKING, datetime.now(timezone.utc))
    overlay.update(
        build_overlay_view_model(
            aggregate=AggregateStatus(ActivityStatus.WORKING, 1, 0),
            badge=BadgeState(completion=True),
            quota_rows=(
                QuotaRow("5 小时", 73, "14:30 刷新", mode="5h"),
                QuotaRow("7 天", 41, "周一 09:00 刷新", mode="7d"),
            ),
            quota_mode="5h",
            tasks=(task,),
            health_text="Codex 事件桥已连接",
        )
    )
    overlay.show()
    root.after(max(100, int(args.duration * 1000)), root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
