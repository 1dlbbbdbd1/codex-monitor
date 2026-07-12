from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .activity_models import ActivityEvent, ActivityStatus, ActivityValidationError, TaskProjection
from .file_locations import ACTIVITY_EVENTS_FILE, ACTIVITY_STATE_FILE


_STATE_VERSION = 1
_RECENT_EVENT_LIMIT = 4096


def _format_datetime(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be text")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _event_payload(event: ActivityEvent) -> dict[str, Any]:
    return {
        "schemaVersion": event.schema_version,
        "eventId": str(event.event_id),
        "eventType": event.event_type.value,
        "threadId": event.thread_id,
        "turnId": event.turn_id,
        "taskTitle": event.task_title,
        "projectName": event.project_name,
        "cwd": event.cwd,
        "occurredAt": _format_datetime(event.occurred_at),
        "source": event.source,
    }


def append_event(path: Path, event: ActivityEvent) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = (json.dumps(_event_payload(event), ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        written = os.write(descriptor, line)
        if written != len(line):
            raise OSError(f"short activity event write: {written}/{len(line)}")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@dataclass(frozen=True, slots=True)
class ActivitySnapshot:
    tasks: dict[str, TaskProjection]
    applied_event_count: int
    rejected_event_count: int


class ActivityStore:
    def __init__(
        self,
        events_path: Path = ACTIVITY_EVENTS_FILE,
        state_path: Path = ACTIVITY_STATE_FILE,
    ) -> None:
        self.events_path = events_path
        self.state_path = state_path
        self.byte_offset = 0
        self.tasks: dict[str, TaskProjection] = {}
        self._recent_event_ids: list[str] = []
        self._recent_event_id_set: set[str] = set()
        self._load()

    def poll(self) -> ActivitySnapshot:
        if not self.events_path.exists():
            return self._snapshot(0, 0)

        file_size = self.events_path.stat().st_size
        if file_size < self.byte_offset:
            self.byte_offset = 0

        with self.events_path.open("rb") as handle:
            handle.seek(self.byte_offset)
            pending = handle.read()

        last_newline = pending.rfind(b"\n")
        if last_newline < 0:
            return self._snapshot(0, 0)

        complete = pending[: last_newline + 1]
        applied = 0
        rejected = 0
        for raw_line in complete.splitlines():
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line.decode("utf-8"))
                event = ActivityEvent.from_dict(payload)
            except (UnicodeDecodeError, json.JSONDecodeError, ActivityValidationError, TypeError):
                rejected += 1
                continue

            event_id = str(event.event_id)
            if event_id in self._recent_event_id_set:
                continue

            task = self.tasks.get(event.thread_id)
            if task is None:
                task = TaskProjection.from_event(event)
                self.tasks[event.thread_id] = task
            else:
                task.apply(event)
            self._remember_event_id(event_id)
            applied += 1

        self.byte_offset += len(complete)
        return self._snapshot(applied, rejected)

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _STATE_VERSION,
            "byteOffset": self.byte_offset,
            "recentEventIds": self._recent_event_ids,
            "tasks": {thread_id: self._task_payload(task) for thread_id, task in sorted(self.tasks.items())},
        }
        temporary = self.state_path.with_suffix(f"{self.state_path.suffix}.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.state_path)

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            if payload.get("version") != _STATE_VERSION:
                return
            self.byte_offset = max(0, int(payload.get("byteOffset", 0)))
            recent = [str(value) for value in payload.get("recentEventIds", [])][-_RECENT_EVENT_LIMIT:]
            self._recent_event_ids = recent
            self._recent_event_id_set = set(recent)
            raw_tasks = payload.get("tasks", {})
            if isinstance(raw_tasks, dict):
                self.tasks = {
                    str(thread_id): self._task_from_payload(str(thread_id), value)
                    for thread_id, value in raw_tasks.items()
                    if isinstance(value, dict)
                }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.byte_offset = 0
            self.tasks = {}
            self._recent_event_ids = []
            self._recent_event_id_set = set()

    def _remember_event_id(self, event_id: str) -> None:
        self._recent_event_ids.append(event_id)
        self._recent_event_id_set.add(event_id)
        if len(self._recent_event_ids) <= _RECENT_EVENT_LIMIT:
            return
        removed = self._recent_event_ids.pop(0)
        self._recent_event_id_set.discard(removed)

    def _snapshot(self, applied: int, rejected: int) -> ActivitySnapshot:
        return ActivitySnapshot(tasks=dict(self.tasks), applied_event_count=applied, rejected_event_count=rejected)

    @staticmethod
    def _task_payload(task: TaskProjection) -> dict[str, Any]:
        return {
            "turnId": task.turn_id,
            "taskTitle": task.task_title,
            "projectName": task.project_name,
            "cwd": task.cwd,
            "status": task.status.value,
            "updatedAt": _format_datetime(task.updated_at),
        }

    @staticmethod
    def _task_from_payload(thread_id: str, payload: dict[str, Any]) -> TaskProjection:
        return TaskProjection(
            thread_id=thread_id,
            turn_id=payload.get("turnId"),
            task_title=payload.get("taskTitle"),
            project_name=payload.get("projectName"),
            cwd=payload.get("cwd"),
            status=ActivityStatus(str(payload["status"])),
            updated_at=_parse_datetime(payload["updatedAt"]),
        )
