from __future__ import annotations

import json
import os
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .file_locations import COMPANION_SUPPORT_DIRECTORY


_STATUS_PREFIX = "Codex Floating Companion · "
_HOOK_EVENTS = ("UserPromptSubmit", "PermissionRequest", "PostToolUse", "Stop")


class HookInstallError(RuntimeError):
    """The user's hook file could not be updated safely."""


def count_companion_hooks(payload: dict[str, Any]) -> int:
    return sum(1 for _ in _iter_companion_handlers(payload))


def _iter_companion_handlers(payload: dict[str, Any]):
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        return
    for groups in hooks.values():
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, dict):
                continue
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                continue
            for handler in handlers:
                if isinstance(handler, dict) and str(handler.get("statusMessage", "")).startswith(_STATUS_PREFIX):
                    yield handler


class HookInstaller:
    def __init__(self, hooks_path: Path | None = None, backup_dir: Path | None = None) -> None:
        self.hooks_path = hooks_path or (Path.home() / ".codex" / "hooks.json")
        self.backup_dir = backup_dir or (COMPANION_SUPPORT_DIRECTORY / "hook-backups")

    def install(self, executable: Path) -> None:
        original_bytes, payload = self._read()
        updated = self._without_companion_handlers(deepcopy(payload))
        hooks = updated.setdefault("hooks", {})
        assert isinstance(hooks, dict)
        command = subprocess.list2cmdline([str(executable), "--emit-hook"])
        for event_name in _HOOK_EVENTS:
            groups = hooks.setdefault(event_name, [])
            if not isinstance(groups, list):
                raise HookInstallError(f"hooks.{event_name} must be a list")
            groups.append(
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": command,
                            "commandWindows": command,
                            "timeout": 5,
                            "async": True,
                            "statusMessage": f"{_STATUS_PREFIX}{event_name}",
                        }
                    ]
                }
            )
        self._replace_if_changed(original_bytes, payload, updated)

    def uninstall(self) -> None:
        if not self.hooks_path.exists():
            return
        original_bytes, payload = self._read()
        updated = self._without_companion_handlers(deepcopy(payload))
        self._replace_if_changed(original_bytes, payload, updated)

    def _read(self) -> tuple[bytes | None, dict[str, Any]]:
        if not self.hooks_path.exists():
            return None, {"hooks": {}}
        try:
            original = self.hooks_path.read_bytes()
            payload = json.loads(original.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HookInstallError("Existing Codex hooks.json is not valid UTF-8 JSON") from error
        if not isinstance(payload, dict):
            raise HookInstallError("Existing Codex hooks.json root must be an object")
        hooks = payload.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise HookInstallError("Existing Codex hooks.json hooks must be an object")
        return original, payload

    def _without_companion_handlers(self, payload: dict[str, Any]) -> dict[str, Any]:
        hooks = payload.get("hooks")
        if not isinstance(hooks, dict):
            raise HookInstallError("Codex hooks must be an object")
        for event_name, groups in list(hooks.items()):
            if not isinstance(groups, list):
                raise HookInstallError(f"hooks.{event_name} must be a list")
            kept_groups: list[Any] = []
            for group in groups:
                if not isinstance(group, dict):
                    kept_groups.append(group)
                    continue
                handlers = group.get("hooks")
                if not isinstance(handlers, list):
                    kept_groups.append(group)
                    continue
                kept_handlers = [
                    handler
                    for handler in handlers
                    if not (
                        isinstance(handler, dict)
                        and str(handler.get("statusMessage", "")).startswith(_STATUS_PREFIX)
                    )
                ]
                if kept_handlers:
                    group["hooks"] = kept_handlers
                    kept_groups.append(group)
            if kept_groups:
                hooks[event_name] = kept_groups
            else:
                hooks.pop(event_name, None)
        return payload

    def _replace_if_changed(
        self,
        original_bytes: bytes | None,
        original_payload: dict[str, Any],
        updated_payload: dict[str, Any],
    ) -> None:
        if original_payload == updated_payload:
            return
        self.hooks_path.parent.mkdir(parents=True, exist_ok=True)
        if original_bytes is not None:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            backup = self.backup_dir / f"hooks.{stamp}.json"
            backup.write_bytes(original_bytes)
        temporary = self.hooks_path.with_suffix(f"{self.hooks_path.suffix}.tmp")
        temporary.write_text(
            json.dumps(updated_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.hooks_path)
