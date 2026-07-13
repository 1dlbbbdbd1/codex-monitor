from __future__ import annotations

import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from codexcontrol_windows.activity_models import ActivityEvent, ActivityStatus, EventType
from codexcontrol_windows.activity_store import ActivityStore, append_event
from codexcontrol_windows.app import activity_connection_health, activity_poll_render_decision


NOW = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)


def event(event_id: int, event_type: EventType, *, thread_id: str = "thread-a") -> ActivityEvent:
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


def payload(event_id: int, event_type: str, *, thread_id: str = "thread-a") -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "eventId": str(UUID(int=event_id)),
        "eventType": event_type,
        "threadId": thread_id,
        "turnId": "turn-a",
        "taskTitle": "Build companion",
        "projectName": "Companion",
        "cwd": "C:/work/companion",
        "occurredAt": (NOW + timedelta(seconds=event_id)).isoformat().replace("+00:00", "Z"),
        "source": "hook",
    }


class ActivityStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.events = self.root / "activity-events.jsonl"
        self.state = self.root / "activity-state.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_append_and_poll_projects_task_state(self) -> None:
        append_event(self.events, event(1, EventType.TURN_STARTED))
        append_event(self.events, event(2, EventType.APPROVAL_REQUESTED))

        snapshot = ActivityStore(self.events, self.state).poll()

        self.assertEqual(snapshot.applied_event_count, 2)
        self.assertEqual(snapshot.rejected_event_count, 0)
        self.assertEqual(snapshot.tasks["thread-a"].status, ActivityStatus.WAITING_APPROVAL)
        self.assertEqual(
            [event.event_type for event in snapshot.applied_events],
            [EventType.TURN_STARTED, EventType.APPROVAL_REQUESTED],
        )

    def test_duplicate_event_id_is_applied_once(self) -> None:
        duplicate = event(1, EventType.TURN_STARTED)
        append_event(self.events, duplicate)
        append_event(self.events, duplicate)

        snapshot = ActivityStore(self.events, self.state).poll()

        self.assertEqual(snapshot.applied_event_count, 1)
        self.assertEqual(len(snapshot.tasks), 1)

    def test_poll_keeps_offset_before_incomplete_tail(self) -> None:
        first_line = json.dumps(payload(1, "turn_started"), separators=(",", ":")).encode("utf-8") + b"\n"
        second_line = json.dumps(payload(2, "turn_completed"), separators=(",", ":")).encode("utf-8") + b"\n"
        split_at = len(second_line) // 2
        self.events.write_bytes(first_line + second_line[:split_at])
        store = ActivityStore(self.events, self.state)

        first = store.poll()
        self.assertEqual(first.applied_event_count, 1)
        self.assertEqual(first.tasks["thread-a"].status, ActivityStatus.WORKING)

        with self.events.open("ab") as handle:
            handle.write(second_line[split_at:])
        second = store.poll()

        self.assertEqual(second.applied_event_count, 1)
        self.assertEqual(second.tasks["thread-a"].status, ActivityStatus.COMPLETED)

    def test_bad_line_is_rejected_without_stopping_later_events(self) -> None:
        valid_one = json.dumps(payload(1, "turn_started"), separators=(",", ":"))
        valid_two = json.dumps(payload(2, "turn_completed"), separators=(",", ":"))
        self.events.write_text(f"{valid_one}\nnot-json\n{valid_two}\n", encoding="utf-8")

        snapshot = ActivityStore(self.events, self.state).poll()

        self.assertEqual(snapshot.applied_event_count, 2)
        self.assertEqual(snapshot.rejected_event_count, 1)
        self.assertEqual(snapshot.tasks["thread-a"].status, ActivityStatus.COMPLETED)

    def test_saved_projection_and_offset_restore_after_restart(self) -> None:
        append_event(self.events, event(1, EventType.TURN_STARTED))
        first_store = ActivityStore(self.events, self.state)
        first_store.poll()
        first_store.save()
        append_event(self.events, event(2, EventType.TURN_COMPLETED))

        restored = ActivityStore(self.events, self.state).poll()

        self.assertEqual(restored.applied_event_count, 1)
        self.assertEqual(restored.tasks["thread-a"].status, ActivityStatus.COMPLETED)


class ActivityPollRenderDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.events = self.root / "activity-events.jsonl"
        self.state = self.root / "activity-state.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_unchanged_idle_poll_does_not_request_render(self) -> None:
        snapshot = ActivityStore(self.events, self.state).poll()

        health, should_render = activity_poll_render_decision(
            current_health="Codex 状态连接正常",
            snapshot=snapshot,
            error=None,
            events_file_exists=True,
        )

        self.assertEqual(health, "Codex 状态连接正常")
        self.assertFalse(should_render)

    def test_new_activity_event_requests_render(self) -> None:
        append_event(self.events, event(1, EventType.TURN_STARTED))
        snapshot = ActivityStore(self.events, self.state).poll()

        health, should_render = activity_poll_render_decision(
            current_health="Codex 状态连接正常",
            snapshot=snapshot,
            error=None,
            events_file_exists=True,
        )

        self.assertEqual(health, "Codex 状态连接正常")
        self.assertTrue(should_render)


class ActivityConnectionHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path("test-artifacts") / "activity-connection-health"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = self.root / "activity-events.jsonl"
        self.state = self.root / "activity-state.json"
        self.events.unlink(missing_ok=True)
        self.state.unlink(missing_ok=True)
        self.now = datetime(2026, 7, 13, 9, 30, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.events.unlink(missing_ok=True)
        self.state.unlink(missing_ok=True)
        try:
            self.root.rmdir()
            self.root.parent.rmdir()
        except OSError:
            pass

    def test_missing_events_file_reports_not_connected(self) -> None:
        health = activity_connection_health(self.events, now=self.now)

        self.assertEqual(health, "状态连接未收到事件")

    def test_recent_events_file_reports_connected(self) -> None:
        self.events.write_text("", encoding="utf-8")
        os.utime(self.events, (self.now.timestamp(), self.now.timestamp()))

        health = activity_connection_health(self.events, now=self.now)

        self.assertEqual(health, "Codex 状态连接正常")

    def test_stale_events_file_reports_repair_needed(self) -> None:
        stale_time = self.now - timedelta(minutes=30)
        self.events.write_text("", encoding="utf-8")
        os.utime(self.events, (stale_time.timestamp(), stale_time.timestamp()))

        health = activity_connection_health(self.events, now=self.now)

        self.assertEqual(health, "状态连接陈旧，请修复")

    def test_first_successful_connection_status_requests_render(self) -> None:
        snapshot = ActivityStore(self.events, self.state).poll()

        health, should_render = activity_poll_render_decision(
            current_health="等待 Codex 事件",
            snapshot=snapshot,
            error=None,
            events_file_exists=True,
        )

        self.assertEqual(health, "Codex 状态连接正常")
        self.assertTrue(should_render)


if __name__ == "__main__":
    unittest.main()
