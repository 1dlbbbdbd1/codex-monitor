from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable
from uuid import UUID


class ActivityValidationError(ValueError):
    """An activity payload is invalid or contains unsupported data."""


class ActivityStatus(str, Enum):
    UNKNOWN = "unknown"
    IDLE = "idle"
    WORKING = "working"
    WAITING_APPROVAL = "waitingApproval"
    COMPLETED = "completed"
    FAILED = "failed"


class EventType(str, Enum):
    TURN_STARTED = "turn_started"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    TURN_COMPLETED = "turn_completed"
    TURN_FAILED = "turn_failed"
    TURN_INTERRUPTED = "turn_interrupted"
    HEARTBEAT = "heartbeat"


_ALLOWED_EVENT_KEYS = {
    "schemaVersion",
    "eventId",
    "eventType",
    "threadId",
    "turnId",
    "taskTitle",
    "projectName",
    "cwd",
    "occurredAt",
    "source",
}


def _clean_text(value: Any, *, field: str, limit: int, required: bool = False) -> str | None:
    if value is None:
        if required:
            raise ActivityValidationError(f"{field} is required")
        return None
    if not isinstance(value, str):
        raise ActivityValidationError(f"{field} must be text")

    cleaned = value.strip()
    if required and not cleaned:
        raise ActivityValidationError(f"{field} is required")
    if not cleaned:
        return None
    if len(cleaned) > limit:
        raise ActivityValidationError(f"{field} exceeds {limit} characters")
    if any(unicodedata.category(character) == "Cc" for character in cleaned):
        raise ActivityValidationError(f"{field} contains control characters")
    return cleaned


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ActivityValidationError("occurredAt is required")
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ActivityValidationError("occurredAt must be ISO-8601") from error
    if parsed.tzinfo is None:
        raise ActivityValidationError("occurredAt must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ActivityEvent:
    schema_version: int
    event_id: UUID
    event_type: EventType
    thread_id: str
    turn_id: str | None
    task_title: str | None
    project_name: str | None
    cwd: str | None
    occurred_at: datetime
    source: str

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ActivityEvent":
        if not isinstance(payload, dict):
            raise ActivityValidationError("activity event must be an object")

        unsupported = set(payload) - _ALLOWED_EVENT_KEYS
        if unsupported:
            raise ActivityValidationError(f"unsupported activity fields: {', '.join(sorted(unsupported))}")
        if payload.get("schemaVersion") != 1:
            raise ActivityValidationError("unsupported schemaVersion")

        try:
            event_id = UUID(str(payload.get("eventId")))
        except (ValueError, TypeError, AttributeError) as error:
            raise ActivityValidationError("eventId must be a UUID") from error
        try:
            event_type = EventType(str(payload.get("eventType")))
        except ValueError as error:
            raise ActivityValidationError("unsupported eventType") from error

        thread_id = _clean_text(payload.get("threadId"), field="threadId", limit=128, required=True)
        source = _clean_text(payload.get("source"), field="source", limit=32, required=True)
        assert thread_id is not None
        assert source is not None

        return cls(
            schema_version=1,
            event_id=event_id,
            event_type=event_type,
            thread_id=thread_id,
            turn_id=_clean_text(payload.get("turnId"), field="turnId", limit=128),
            task_title=_clean_text(payload.get("taskTitle"), field="taskTitle", limit=256),
            project_name=_clean_text(payload.get("projectName"), field="projectName", limit=128),
            cwd=_clean_text(payload.get("cwd"), field="cwd", limit=1024),
            occurred_at=_parse_timestamp(payload.get("occurredAt")),
            source=source,
        )


_EVENT_STATUS = {
    EventType.TURN_STARTED: ActivityStatus.WORKING,
    EventType.APPROVAL_REQUESTED: ActivityStatus.WAITING_APPROVAL,
    EventType.APPROVAL_RESOLVED: ActivityStatus.WORKING,
    EventType.TURN_COMPLETED: ActivityStatus.COMPLETED,
    EventType.TURN_FAILED: ActivityStatus.FAILED,
    EventType.TURN_INTERRUPTED: ActivityStatus.IDLE,
}


@dataclass(slots=True)
class TaskProjection:
    thread_id: str
    turn_id: str | None
    task_title: str | None
    project_name: str | None
    cwd: str | None
    status: ActivityStatus
    updated_at: datetime

    @classmethod
    def from_event(cls, activity_event: ActivityEvent) -> "TaskProjection":
        projection = cls(
            thread_id=activity_event.thread_id,
            turn_id=activity_event.turn_id,
            task_title=activity_event.task_title,
            project_name=activity_event.project_name,
            cwd=activity_event.cwd,
            status=ActivityStatus.UNKNOWN,
            updated_at=activity_event.occurred_at,
        )
        projection.apply(activity_event)
        return projection

    def apply(self, activity_event: ActivityEvent) -> None:
        if activity_event.thread_id != self.thread_id:
            raise ActivityValidationError("event thread does not match task projection")
        if activity_event.occurred_at < self.updated_at:
            return

        self.turn_id = activity_event.turn_id or self.turn_id
        self.task_title = activity_event.task_title or self.task_title
        self.project_name = activity_event.project_name or self.project_name
        self.cwd = activity_event.cwd or self.cwd
        self.status = _EVENT_STATUS.get(activity_event.event_type, self.status)
        self.updated_at = activity_event.occurred_at


@dataclass(frozen=True, slots=True)
class AggregateStatus:
    status: ActivityStatus
    working_count: int
    attention_count: int


def aggregate_tasks(tasks: Iterable[TaskProjection]) -> AggregateStatus:
    materialized = list(tasks)
    priority = {
        ActivityStatus.WAITING_APPROVAL: 0,
        ActivityStatus.FAILED: 1,
        ActivityStatus.WORKING: 2,
        ActivityStatus.COMPLETED: 3,
        ActivityStatus.IDLE: 4,
        ActivityStatus.UNKNOWN: 5,
    }
    selected = min(
        (task.status for task in materialized),
        key=priority.__getitem__,
        default=ActivityStatus.IDLE,
    )
    return AggregateStatus(
        status=selected,
        working_count=sum(task.status is ActivityStatus.WORKING for task in materialized),
        attention_count=sum(task.status is ActivityStatus.WAITING_APPROVAL for task in materialized),
    )
