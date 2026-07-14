# Quota Dial and Live Activity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a switchable quota percentage on the floating ball and make Codex lifecycle hooks emit live task events.

**Architecture:** Extend the existing overlay settings with one quota mode, derive the displayed quota in the existing view-model builder, and draw one supersampled progress dial. Keep the existing JSONL activity bridge and make its command hooks synchronous as required by Codex.

**Tech Stack:** Python 3, tkinter, Pillow, unittest, JSON/JSONL

## Global Constraints

- No new dependency or framework.
- Default quota mode is `5h`; supported modes are `5h` and `7d`.
- Missing selected quota falls back to an available quota.
- Hook payload handling must not record prompts, commands, tool inputs, or responses.

---

### Task 1: Persist quota mode

**Files:**
- Modify: `windows/tests/test_settings_store.py`
- Modify: `windows/codexcontrol_windows/settings_store.py`

- [ ] Add failing round-trip and update-helper assertions for `quota_mode`.
- [ ] Run `python -m unittest windows.tests.test_settings_store -v` and confirm the new assertions fail.
- [ ] Add `quota_mode: str = "5h"`, JSON persistence, and a preserving update helper.
- [ ] Re-run the test and confirm it passes.

### Task 2: Select and render quota on the ball

**Files:**
- Modify: `windows/tests/test_app_integration.py`
- Modify: `windows/tests/test_brand_icon.py`
- Modify: `windows/codexcontrol_windows/brand_icon.py`
- Modify: `windows/codexcontrol_windows/floating_overlay.py`
- Modify: `windows/codexcontrol_windows/app.py`

- [ ] Add failing tests for `5h` default selection, `7d` selection, fallback, and a variable progress dial.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Add the minimum view-model fields, persisted segmented switch, supersampled dial, percentage text, and quota label.
- [ ] Re-run the focused tests and confirm they pass.

### Task 3: Make live hooks runnable

**Files:**
- Modify: `windows/tests/test_hook_installer.py`
- Modify: `windows/codexcontrol_windows/hook_installer.py`
- Modify: `plugin/codex-floating-companion/hooks/hooks.json`

- [ ] Add a failing assertion that installed companion handlers omit `async`.
- [ ] Run `python -m unittest windows.tests.test_hook_installer -v` and confirm it fails.
- [ ] Remove `async: true` from generated and plugin hook definitions.
- [ ] Re-run the hook and bridge tests and confirm they pass.

### Task 4: Documentation and verification

**Files:**
- Modify: `README.md`
- Modify: `docs/known-limitations.md`

- [ ] Record the quota switch, fallback behavior, synchronous hook fix, and `/hooks` trust requirement.
- [ ] Run focused tests, full Windows tests, compileall, and GUI smoke capture.
- [ ] Inspect the screenshot for text clipping, overlap, ring smoothness, and correct quota label.
