from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import UUID

from codexcontrol_windows.activity_models import (
    ActivityEvent,
    ActivityStatus,
    ActivityValidationError,
    EventType,
    TaskProjection,
    aggregate_tasks,
)


NOW = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)


def event(event_type: EventType, *, event_id: int, thread_id: str = "thread-a") -> ActivityEvent:
    return ActivityEvent(
        schema_version=1,
        event_id=UUID(int=event_id),
        event_type=event_type,
        thread_id=thread_id,
        turn_id="turn-a",
        task_title="Build companion",
        project_name="Companion",
        cwd="C:/work/companion",
        occurred_at=NOW,
        source="hook",
    )


class ActivityEventTests(unittest.TestCase):
    def test_from_dict_accepts_and_normalizes_allowed_fields(self) -> None:
        parsed = ActivityEvent.from_dict(
            {
                "schemaVersion": 1,
                "eventId": "00000000-0000-0000-0000-000000000001",
                "eventType": "turn_started",
                "threadId": " thread-a ",
                "turnId": "turn-a",
                "taskTitle": " Build companion ",
                "projectName": " Companion ",
                "cwd": " C:/work/companion ",
                "occurredAt": "2026-07-12T12:00:00Z",
                "source": "hook",
            }
        )

        self.assertEqual(parsed.thread_id, "thread-a")
        self.assertEqual(parsed.task_title, "Build companion")
        self.assertEqual(parsed.occurred_at, NOW)

    def test_from_dict_rejects_sensitive_fields(self) -> None:
        payload = {
            "schemaVersion": 1,
            "eventId": "00000000-0000-0000-0000-000000000001",
            "eventType": "turn_started",
            "threadId": "thread-a",
            "occurredAt": "2026-07-12T12:00:00Z",
            "source": "hook",
            "prompt": "secret",
        }

        with self.assertRaises(ActivityValidationError):
            ActivityEvent.from_dict(payload)

    def test_from_dict_rejects_oversized_title(self) -> None:
        payload = {
            "schemaVersion": 1,
            "eventId": "00000000-0000-0000-0000-000000000001",
            "eventType": "turn_started",
            "threadId": "thread-a",
            "taskTitle": "x" * 257,
            "occurredAt": "2026-07-12T12:00:00Z",
            "source": "hook",
        }

        with self.assertRaises(ActivityValidationError):
            ActivityEvent.from_dict(payload)


class TaskProjectionTests(unittest.TestCase):
    def test_projection_moves_through_work_approval_and_completion(self) -> None:
        task = TaskProjection.from_event(event(EventType.TURN_STARTED, event_id=1))
        self.assertEqual(task.status, ActivityStatus.WORKING)

        task.apply(event(EventType.APPROVAL_REQUESTED, event_id=2))
        self.assertEqual(task.status, ActivityStatus.WAITING_APPROVAL)

        task.apply(event(EventType.APPROVAL_RESOLVED, event_id=3))
        self.assertEqual(task.status, ActivityStatus.WORKING)

        task.apply(event(EventType.TURN_COMPLETED, event_id=4))
        self.assertEqual(task.status, ActivityStatus.COMPLETED)

    def test_projection_maps_failure_and_interruption(self) -> None:
        failed = TaskProjection.from_event(event(EventType.TURN_FAILED, event_id=1, thread_id="failed"))
        interrupted = TaskProjection.from_event(event(EventType.TURN_INTERRUPTED, event_id=2, thread_id="stopped"))

        self.assertEqual(failed.status, ActivityStatus.FAILED)
        self.assertEqual(interrupted.status, ActivityStatus.IDLE)


class AggregateTests(unittest.TestCase):
    def test_waiting_approval_has_highest_priority(self) -> None:
        tasks = [
            TaskProjection.from_event(event(EventType.TURN_STARTED, event_id=1, thread_id="working")),
            TaskProjection.from_event(event(EventType.APPROVAL_REQUESTED, event_id=2, thread_id="approval")),
            TaskProjection.from_event(event(EventType.TURN_FAILED, event_id=3, thread_id="failed")),
        ]

        aggregate = aggregate_tasks(tasks)

        self.assertEqual(aggregate.status, ActivityStatus.WAITING_APPROVAL)
        self.assertEqual(aggregate.working_count, 1)
        self.assertEqual(aggregate.attention_count, 1)

    def test_empty_collection_is_idle(self) -> None:
        aggregate = aggregate_tasks([])

        self.assertEqual(aggregate.status, ActivityStatus.IDLE)
        self.assertEqual(aggregate.working_count, 0)
        self.assertEqual(aggregate.attention_count, 0)


if __name__ == "__main__":
    unittest.main()
