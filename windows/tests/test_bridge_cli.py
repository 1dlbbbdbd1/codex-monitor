from __future__ import annotations

import io
import inspect
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from codexcontrol_windows.activity_models import EventType
from codexcontrol_windows.activity_store import ActivityStore
from codexcontrol_windows.bridge_cli import dispatch, main, normalize_hook_payload
from codexcontrol_windows.hook_installer import HookInstaller, count_companion_hooks


NOW = datetime(2026, 7, 12, 12, 0, tzinfo=timezone.utc)


class BridgeNormalizationTests(unittest.TestCase):
    def test_bridge_ignores_prompt_command_and_assistant_message(self) -> None:
        parsed = normalize_hook_payload(
            {
                "hook_event_name": "UserPromptSubmit",
                "session_id": "thread-a",
                "turn_id": "turn-a",
                "cwd": "C:/work/companion",
                "prompt": "private prompt",
                "command": "private command",
                "last_assistant_message": "private response",
            },
            now=NOW,
        )

        self.assertEqual(parsed.event_type, EventType.TURN_STARTED)
        self.assertEqual(parsed.thread_id, "thread-a")
        self.assertEqual(parsed.project_name, "companion")
        self.assertIsNone(parsed.task_title)
        self.assertNotIn("private", repr(parsed))

    def test_bridge_maps_supported_hook_events(self) -> None:
        expected = {
            "UserPromptSubmit": EventType.TURN_STARTED,
            "PermissionRequest": EventType.APPROVAL_REQUESTED,
            "PostToolUse": EventType.APPROVAL_RESOLVED,
            "Stop": EventType.TURN_COMPLETED,
        }

        for hook_name, event_type in expected.items():
            with self.subTest(hook_name=hook_name):
                parsed = normalize_hook_payload(
                    {
                        "hook_event_name": hook_name,
                        "session_id": "thread-a",
                        "turn_id": "turn-a",
                        "cwd": "C:/work/companion",
                    },
                    now=NOW,
                )
                self.assertEqual(parsed.event_type, event_type)


class BridgeMainTests(unittest.TestCase):
    def test_dispatch_skips_gui_when_an_instance_is_already_running(self) -> None:
        self.assertIn("acquire_instance", inspect.signature(dispatch).parameters)
        gui_calls: list[list[str]] = []

        exit_code = dispatch(
            [],
            io.StringIO(""),
            lambda argv: gui_calls.append(argv),
            acquire_instance=lambda: False,
        )

        self.assertEqual(exit_code, 0)
        self.assertEqual(gui_calls, [])

    def test_main_appends_normalized_event(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            events = root / "events.jsonl"
            state = root / "state.json"
            payload = {
                "hook_event_name": "PermissionRequest",
                "session_id": "thread-a",
                "turn_id": "turn-a",
                "cwd": "C:/work/companion",
                "tool_input": {"command": "secret"},
            }

            exit_code = main(["--events-path", str(events)], io.StringIO(json.dumps(payload)), now=NOW)
            snapshot = ActivityStore(events, state).poll()

            self.assertEqual(exit_code, 0)
            self.assertEqual(snapshot.applied_event_count, 1)
            self.assertEqual(snapshot.tasks["thread-a"].project_name, "companion")
            self.assertNotIn("secret", events.read_text(encoding="utf-8"))

    def test_main_fails_softly_for_invalid_input(self) -> None:
        with TemporaryDirectory() as temp_dir:
            events = Path(temp_dir) / "events.jsonl"

            exit_code = main(["--events-path", str(events)], io.StringIO("not-json"), now=NOW)

            self.assertEqual(exit_code, 0)
            self.assertFalse(events.exists())

    def test_dispatch_uses_bridge_mode_without_starting_gui(self) -> None:
        with TemporaryDirectory() as temp_dir:
            events = Path(temp_dir) / "events.jsonl"
            gui_calls: list[list[str]] = []
            payload = {
                "hook_event_name": "Stop",
                "session_id": "thread-a",
                "turn_id": "turn-a",
                "cwd": "C:/work/companion",
            }

            exit_code = dispatch(
                ["--emit-hook", "--events-path", str(events)],
                io.StringIO(json.dumps(payload)),
                lambda argv: gui_calls.append(argv),
                now=NOW,
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(gui_calls, [])
            self.assertTrue(events.exists())

    def test_dispatch_installs_and_uninstalls_hooks_without_starting_gui(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            hooks = root / "hooks.json"
            installer = HookInstaller(hooks, root / "backups")
            gui_calls: list[list[str]] = []

            install_code = dispatch(
                ["--install-hooks"],
                io.StringIO(""),
                lambda argv: gui_calls.append(argv),
                hook_installer=installer,
                executable=root / "CodexFloatingCompanion.exe",
            )
            installed = json.loads(hooks.read_text(encoding="utf-8"))
            uninstall_code = dispatch(
                ["--uninstall-hooks"],
                io.StringIO(""),
                lambda argv: gui_calls.append(argv),
                hook_installer=installer,
            )
            uninstalled = json.loads(hooks.read_text(encoding="utf-8"))

            self.assertEqual((install_code, uninstall_code), (0, 0))
            self.assertEqual(count_companion_hooks(installed), 4)
            self.assertEqual(count_companion_hooks(uninstalled), 0)
            self.assertEqual(gui_calls, [])


if __name__ == "__main__":
    unittest.main()
