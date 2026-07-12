from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID

from codexcontrol_windows.activity_models import ActivityEvent, EventType
from codexcontrol_windows.models import AccountUsageSnapshot, UsageWindowSnapshot
from codexcontrol_windows.notification_state import NotificationState


NOW = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)


def activity(event_type: EventType, *, event_id: int = 1, thread_id: str = "thread-a") -> ActivityEvent:
    return ActivityEvent(
        schema_version=1,
        event_id=UUID(int=event_id),
        event_type=event_type,
        thread_id=thread_id,
        turn_id="turn-a",
        task_title="Build companion",
        project_name="Companion",
        cwd="C:/work/companion",
        occurred_at=NOW + timedelta(seconds=event_id),
        source="hook",
    )


def quota(*, remaining: float, reset_at: datetime) -> AccountUsageSnapshot:
    return AccountUsageSnapshot(
        email="user@example.com",
        provider_account_id="account-a",
        plan="plus",
        allowed=True,
        limit_reached=False,
        primary_window=UsageWindowSnapshot(
            used_percent=100.0 - remaining,
            reset_at=reset_at,
            limit_window_seconds=18_000,
        ),
        secondary_window=None,
        credits=None,
        updated_at=NOW,
    )


class ActivityNotificationTests(unittest.TestCase):
    def test_panel_view_does_not_clear_unresolved_approval(self) -> None:
        state = NotificationState()
        state.observe_activity(activity(EventType.APPROVAL_REQUESTED))

        state.acknowledge_panel_view()

        self.assertTrue(state.badge.approval)
        self.assertTrue(state.badge.visible)

    def test_approval_resolved_clears_approval_badge(self) -> None:
        state = NotificationState()
        state.observe_activity(activity(EventType.APPROVAL_REQUESTED, event_id=1))

        state.observe_activity(activity(EventType.APPROVAL_RESOLVED, event_id=2))

        self.assertFalse(state.badge.approval)

    def test_terminal_event_clears_approval_and_sets_completion(self) -> None:
        state = NotificationState()
        state.observe_activity(activity(EventType.APPROVAL_REQUESTED, event_id=1))

        state.observe_activity(activity(EventType.TURN_COMPLETED, event_id=2))

        self.assertFalse(state.badge.approval)
        self.assertTrue(state.badge.completion)

    def test_panel_view_clears_completion_and_failure(self) -> None:
        state = NotificationState()
        state.observe_activity(activity(EventType.TURN_COMPLETED, event_id=1, thread_id="complete"))
        state.observe_activity(activity(EventType.TURN_FAILED, event_id=2, thread_id="failed"))

        state.acknowledge_panel_view()

        self.assertFalse(state.badge.completion)
        self.assertFalse(state.badge.failure)
        self.assertFalse(state.badge.visible)


class QuotaNotificationTests(unittest.TestCase):
    def test_first_quota_snapshot_does_not_report_reset(self) -> None:
        state = NotificationState()

        state.observe_quota(quota(remaining=5, reset_at=NOW + timedelta(minutes=5)), observed_at=NOW)

        self.assertFalse(state.badge.quota_reset)

    def test_quota_reset_sets_badge_when_window_rolls_and_remaining_increases(self) -> None:
        state = NotificationState()
        previous_reset = NOW + timedelta(minutes=5)
        state.observe_quota(quota(remaining=5, reset_at=previous_reset), observed_at=NOW)

        state.observe_quota(
            quota(remaining=100, reset_at=NOW + timedelta(hours=5)),
            observed_at=previous_reset + timedelta(seconds=1),
        )

        self.assertTrue(state.badge.quota_reset)

    def test_quota_increase_before_reset_does_not_set_badge(self) -> None:
        state = NotificationState()
        reset = NOW + timedelta(minutes=5)
        state.observe_quota(quota(remaining=5, reset_at=reset), observed_at=NOW)

        state.observe_quota(quota(remaining=10, reset_at=reset), observed_at=NOW + timedelta(minutes=1))

        self.assertFalse(state.badge.quota_reset)

    def test_panel_view_clears_quota_reset_badge(self) -> None:
        state = NotificationState()
        previous_reset = NOW + timedelta(minutes=5)
        state.observe_quota(quota(remaining=5, reset_at=previous_reset), observed_at=NOW)
        state.observe_quota(
            quota(remaining=100, reset_at=NOW + timedelta(hours=5)),
            observed_at=previous_reset + timedelta(seconds=1),
        )

        state.acknowledge_panel_view()

        self.assertFalse(state.badge.quota_reset)


if __name__ == "__main__":
    unittest.main()
