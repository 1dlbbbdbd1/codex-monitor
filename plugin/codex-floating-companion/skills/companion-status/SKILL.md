---
name: companion-status
description: Diagnose and repair the local Codex Floating Companion activity integration on Windows. Use when quota still works but task state is unknown, approval badges do not appear, hooks stopped after a Codex update, or the user asks to check or repair the companion connection.
---

# Companion Status

Diagnose the local integration without reading Codex prompts, responses, commands, diffs, or authentication files.

## Check

1. Confirm Windows is in use and locate `%LOCALAPPDATA%\Programs\CodexFloatingCompanion\CodexFloatingCompanion.exe`.
2. Read `%USERPROFILE%\.codex\hooks.json` as JSON.
3. Verify exactly one command handler for each `UserPromptSubmit`, `PermissionRequest`, `PostToolUse`, and `Stop` event whose `statusMessage` starts with `Codex Floating Companion ·`.
4. Check only the existence, size, and modified time of `%APPDATA%\CodexFloatingCompanion\activity-events.jsonl`; do not print its contents unless the user explicitly requests it.
5. Report the connection as:
   - `healthy`: all four hooks exist and the event file has recent writes.
   - `degraded`: all four hooks exist but the event file is stale.
   - `not installed`: companion hooks are absent.
   - `configuration error`: `hooks.json` is invalid JSON or has invalid event shapes.

## Repair

1. Back up `%USERPROFILE%\.codex\hooks.json` before changing it.
2. Run the installed companion with `--install-hooks`.
3. Re-read the hook file and verify the four owned handlers without changing unrelated handlers.
4. Tell the user to restart Codex so the updated hooks are loaded.

Never edit `auth.json`, Codex session databases, packaged Codex application files, or private IPC endpoints.
