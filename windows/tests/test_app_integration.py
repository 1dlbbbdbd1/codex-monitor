from __future__ import annotations

import unittest
from datetime import datetime, timezone

from codexcontrol_windows.activity_models import ActivityStatus, AggregateStatus, TaskProjection
from codexcontrol_windows.floating_overlay import (
    QuotaRow,
    build_overlay_view_model,
)
from codexcontrol_windows.notification_state import BadgeState


NOW = datetime(2026, 7, 13, 4, 0, tzinfo=timezone.utc)


class OverlayViewModelTests(unittest.TestCase):
    def test_waiting_approval_shows_red_badge_and_attention_count(self) -> None:
        model = build_overlay_view_model(
            aggregate=AggregateStatus(ActivityStatus.WAITING_APPROVAL, 0, 2),
            badge=BadgeState(approval=True),
            quota_rows=(),
            tasks=(),
            health_text="已连接",
        )

        self.assertEqual(model.badge_color, "#ef4444")
        self.assertEqual(model.count_text, "2")
        self.assertTrue(model.keep_handle_visible)
        self.assertEqual(model.status_text, "等待审批")

    def test_working_model_contains_compact_quota_and_task_rows(self) -> None:
        task = TaskProjection(
            thread_id="thread-1",
            turn_id="turn-1",
            task_title="构建第一版悬浮球",
            project_name="companion",
            cwd=r"C:\work\companion",
            status=ActivityStatus.WORKING,
            updated_at=NOW,
        )
        quota = QuotaRow(label="5 小时", remaining_percent=73.0, reset_text="14:30 刷新")

        model = build_overlay_view_model(
            aggregate=AggregateStatus(ActivityStatus.WORKING, 1, 0),
            badge=BadgeState(),
            quota_rows=(quota,),
            tasks=(task,),
            health_text="已连接",
        )

        self.assertEqual(model.accent_color, "#3ad06d")
        self.assertEqual(model.count_text, "1")
        self.assertEqual(model.quota_rows[0].remaining_text, "73%")
        self.assertEqual(model.task_rows[0].title, "构建第一版悬浮球")

    def test_informational_badge_is_blue_and_keeps_a_visible_edge_indicator(self) -> None:
        model = build_overlay_view_model(
            aggregate=AggregateStatus(ActivityStatus.COMPLETED, 0, 0),
            badge=BadgeState(completion=True, quota_reset=True),
            quota_rows=(),
            tasks=(),
            health_text="等待 Codex 事件",
        )

        self.assertEqual(model.badge_color, "#38bdf8")
        self.assertTrue(model.keep_handle_visible)
        self.assertEqual(model.health_text, "等待 Codex 事件")


if __name__ == "__main__":
    unittest.main()
