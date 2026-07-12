from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .activity_models import ActivityEvent, EventType
from .models import AccountUsageSnapshot, UsageWindowSnapshot


@dataclass(frozen=True, slots=True)
class BadgeState:
    approval: bool = False
    failure: bool = False
    completion: bool = False
    quota_reset: bool = False

    @property
    def visible(self) -> bool:
        return self.approval or self.failure or self.completion or self.quota_reset


@dataclass(frozen=True, slots=True)
class _QuotaWindowObservation:
    remaining_percent: float
    reset_at: datetime | None


class NotificationState:
    def __init__(self) -> None:
        self._pending_approval_threads: set[str] = set()
        self._failure = False
        self._completion = False
        self._quota_reset = False
        self._quota_windows: dict[int, _QuotaWindowObservation] = {}

    @property
    def badge(self) -> BadgeState:
        return BadgeState(
            approval=bool(self._pending_approval_threads),
            failure=self._failure,
            completion=self._completion,
            quota_reset=self._quota_reset,
        )

    def observe_activity(self, event: ActivityEvent) -> None:
        if event.event_type is EventType.APPROVAL_REQUESTED:
            self._pending_approval_threads.add(event.thread_id)
            return
        if event.event_type is EventType.APPROVAL_RESOLVED:
            self._pending_approval_threads.discard(event.thread_id)
            return
        if event.event_type in {
            EventType.TURN_COMPLETED,
            EventType.TURN_FAILED,
            EventType.TURN_INTERRUPTED,
        }:
            self._pending_approval_threads.discard(event.thread_id)
        if event.event_type is EventType.TURN_COMPLETED:
            self._completion = True
        elif event.event_type is EventType.TURN_FAILED:
            self._failure = True

    def observe_quota(self, snapshot: AccountUsageSnapshot, *, observed_at: datetime) -> None:
        for window in (snapshot.primary_window, snapshot.secondary_window):
            if window is None:
                continue
            previous = self._quota_windows.get(window.limit_window_seconds)
            if previous is not None and self._window_reset(previous, window, observed_at):
                self._quota_reset = True
            self._quota_windows[window.limit_window_seconds] = _QuotaWindowObservation(
                remaining_percent=window.remaining_percent,
                reset_at=window.reset_at,
            )

    def acknowledge_panel_view(self) -> None:
        self._failure = False
        self._completion = False
        self._quota_reset = False

    @staticmethod
    def _window_reset(
        previous: _QuotaWindowObservation,
        current: UsageWindowSnapshot,
        observed_at: datetime,
    ) -> bool:
        if previous.reset_at is None or current.reset_at is None:
            return False
        return (
            observed_at >= previous.reset_at
            and current.reset_at > previous.reset_at
            and current.remaining_percent > previous.remaining_percent
        )
