from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TextIO
from uuid import uuid4

from .activity_models import ActivityEvent, ActivityValidationError, EventType
from .activity_store import append_event
from .file_locations import ACTIVITY_EVENTS_FILE


_HOOK_EVENT_MAP = {
    "UserPromptSubmit": EventType.TURN_STARTED,
    "PermissionRequest": EventType.APPROVAL_REQUESTED,
    "PostToolUse": EventType.APPROVAL_RESOLVED,
    "Stop": EventType.TURN_COMPLETED,
}


def normalize_hook_payload(payload: dict[str, object], *, now: datetime | None = None) -> ActivityEvent:
    hook_name = payload.get("hook_event_name")
    try:
        event_type = _HOOK_EVENT_MAP[str(hook_name)]
    except KeyError as error:
        raise ActivityValidationError("unsupported Codex hook event") from error

    thread_id = payload.get("session_id")
    if not isinstance(thread_id, str) or not thread_id.strip():
        raise ActivityValidationError("Codex hook payload has no session_id")

    cwd = payload.get("cwd")
    cleaned_cwd = cwd.strip() if isinstance(cwd, str) and cwd.strip() else None
    project_name = Path(cleaned_cwd).name if cleaned_cwd else None
    occurred_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

    return ActivityEvent.from_dict(
        {
            "schemaVersion": 1,
            "eventId": str(uuid4()),
            "eventType": event_type.value,
            "threadId": thread_id,
            "turnId": payload.get("turn_id"),
            "taskTitle": None,
            "projectName": project_name,
            "cwd": cleaned_cwd,
            "occurredAt": occurred_at.isoformat().replace("+00:00", "Z"),
            "source": "hook",
        }
    )


def main(argv: list[str] | None = None, stdin: TextIO | None = None, *, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--events-path", type=Path, default=ACTIVITY_EVENTS_FILE)
    try:
        arguments, _ = parser.parse_known_args(argv or [])
        payload = json.load(stdin or sys.stdin)
        event = normalize_hook_payload(payload, now=now)
        append_event(arguments.events_path, event)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, ActivityValidationError, SystemExit):
        # Observability must never block a Codex turn or approval flow.
        return 0
    return 0


def dispatch(
    argv: list[str],
    stdin: TextIO,
    gui_main: Callable[[list[str]], None],
    *,
    now: datetime | None = None,
) -> int:
    if "--emit-hook" in argv:
        bridge_arguments = [argument for argument in argv if argument != "--emit-hook"]
        return main(bridge_arguments, stdin, now=now)
    gui_main(argv)
    return 0
