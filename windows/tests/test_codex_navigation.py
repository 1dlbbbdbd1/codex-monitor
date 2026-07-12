from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import Mock

from codexcontrol_windows.activity_models import ActivityStatus, TaskProjection
from codexcontrol_windows.codex_navigation import CodexNavigator, NavigationMode


def make_task() -> TaskProjection:
    return TaskProjection(
        thread_id="thread-1",
        turn_id="turn-1",
        task_title="Demo",
        project_name="companion",
        cwd=r"C:\work\companion",
        status=ActivityStatus.WORKING,
        updated_at=datetime.now(timezone.utc),
    )


class CodexNavigatorTests(unittest.TestCase):
    def test_open_task_falls_back_to_foreground_without_private_state_edits(self) -> None:
        foreground = Mock(return_value=True)
        navigator = CodexNavigator(foreground=foreground)

        result = navigator.open_task(make_task(), precise_handler=None)

        self.assertEqual(result.mode, NavigationMode.FOREGROUND_FALLBACK)
        self.assertTrue(result.succeeded)
        foreground.assert_called_once_with()

    def test_precise_handler_is_used_when_available(self) -> None:
        foreground = Mock(return_value=True)
        precise = Mock(return_value=True)
        task = make_task()

        result = CodexNavigator(foreground=foreground).open_task(task, precise_handler=precise)

        self.assertEqual(result.mode, NavigationMode.PRECISE)
        precise.assert_called_once_with(task)
        foreground.assert_not_called()

    def test_failed_precise_handler_safely_falls_back(self) -> None:
        foreground = Mock(return_value=False)
        precise = Mock(side_effect=RuntimeError("unsupported"))

        result = CodexNavigator(foreground=foreground).open_task(make_task(), precise_handler=precise)

        self.assertEqual(result.mode, NavigationMode.FOREGROUND_FALLBACK)
        self.assertFalse(result.succeeded)


if __name__ == "__main__":
    unittest.main()
