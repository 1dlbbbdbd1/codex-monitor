# Codex Companion UI Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Windows floating companion easier to read, closer to Codex-style dark/green visuals, less jagged, and honest about stale task activity.

**Architecture:** Keep the existing Tk/Pillow implementation. Add a small theme helper for shared color tokens and contrast checks, extend overlay settings with a persisted topmost toggle, render the orbit icon with supersampling, and expose activity connection freshness in the overlay model instead of showing stale task data as current.

**Tech Stack:** Python 3.11+, tkinter, Pillow, pystray, unittest, PowerShell.

## Global Constraints

- Do not replace the Tk desktop architecture in this iteration.
- Keep the palette close to Codex: near-black surfaces, mint/green interaction accents, and restrained status colors.
- Do not collect prompts, commands, tool inputs, assistant replies, or auth tokens.
- Use TDD: write failing tests before implementation code.
- Keep docs in sync in `README.md`.

---

### Task 1: Shared Readable Codex Palette

**Files:**
- Create: `windows/codexcontrol_windows/ui_theme.py`
- Modify: `windows/codexcontrol_windows/app.py`
- Modify: `windows/codexcontrol_windows/floating_overlay.py`
- Test: `windows/tests/test_ui_theme.py`

**Interfaces:**
- Produces: `CODEX_DARK_PALETTE: dict[str, str]`
- Produces: `contrast_ratio(foreground: str, background: str) -> float`
- Consumes: existing Tk color strings.

- [ ] **Step 1: Write failing contrast tests**

```python
def test_primary_text_contrast_is_readable():
    from codexcontrol_windows.ui_theme import CODEX_DARK_PALETTE, contrast_ratio
    assert contrast_ratio(CODEX_DARK_PALETTE["text"], CODEX_DARK_PALETTE["shell"]) >= 7.0
    assert contrast_ratio(CODEX_DARK_PALETTE["muted"], CODEX_DARK_PALETTE["shell"]) >= 4.5
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `$env:PYTHONPATH = (Resolve-Path .\windows); .\.venv\Scripts\python.exe -m unittest windows.tests.test_ui_theme -v`

Expected: import failure for `codexcontrol_windows.ui_theme`.

- [ ] **Step 3: Implement the palette helper**

Create `ui_theme.py` with a Codex-like dark palette and WCAG contrast helper.

- [ ] **Step 4: Apply the palette to app and overlay**

Replace duplicated low-contrast colors in `app.py` and `floating_overlay.py` with the shared palette where practical.

- [ ] **Step 5: Run the theme tests**

Expected: `test_ui_theme` passes.

### Task 2: Smooth Orbit Icon Rendering

**Files:**
- Modify: `windows/codexcontrol_windows/brand_icon.py`
- Test: `windows/tests/test_brand_icon.py`

**Interfaces:**
- Produces: `build_orbit_dial_icon(..., scale_factor: int = 4) -> Image.Image`
- Consumes: existing callers, no caller changes required.

- [ ] **Step 1: Write failing supersampling test**

```python
def test_icon_is_rendered_at_requested_size_after_supersampling():
    image = build_orbit_dial_icon(56, accent="#2dd4bf")
    assert image.size == (56, 56)
    assert image.mode == "RGBA"
```

Also assert the alpha edge has multiple intermediate values, proving antialiasing exists instead of a hard stair-step edge.

- [ ] **Step 2: Run brand icon tests to verify the new test fails if needed**

Run: `$env:PYTHONPATH = (Resolve-Path .\windows); .\.venv\Scripts\python.exe -m unittest windows.tests.test_brand_icon -v`

- [ ] **Step 3: Implement supersampling**

Draw at `size * scale_factor`, then downsample with `Image.Resampling.LANCZOS`.

- [ ] **Step 4: Run brand icon tests**

Expected: all brand icon tests pass.

### Task 3: Persisted Topmost Toggle

**Files:**
- Modify: `windows/codexcontrol_windows/settings_store.py`
- Modify: `windows/codexcontrol_windows/floating_overlay.py`
- Modify: `windows/codexcontrol_windows/app.py`
- Test: `windows/tests/test_settings_store.py`

**Interfaces:**
- Extends: `OverlaySettings(always_on_top: bool = True)`
- Produces: `overlay_settings_with_topmost(settings: OverlaySettings, always_on_top: bool) -> OverlaySettings`
- Consumes: existing `FloatingOverlay.settings`.

- [ ] **Step 1: Write failing settings tests**

Add a test that saves `OverlaySettings(always_on_top=False)` and verifies it round-trips.

- [ ] **Step 2: Run settings tests to verify failure**

Run: `$env:PYTHONPATH = (Resolve-Path .\windows); .\.venv\Scripts\python.exe -m unittest windows.tests.test_settings_store -v`

- [ ] **Step 3: Implement setting storage and overlay application**

Persist `alwaysOnTop`, call `window.attributes("-topmost", settings.always_on_top)`, and add a tray menu item `置顶悬浮球` / `取消置顶`.

- [ ] **Step 4: Run settings tests**

Expected: settings tests pass.

### Task 4: Honest Activity Freshness

**Files:**
- Modify: `windows/codexcontrol_windows/app.py`
- Modify: `windows/codexcontrol_windows/floating_overlay.py`
- Test: `windows/tests/test_app_integration.py`
- Test: `windows/tests/test_activity_store.py`

**Interfaces:**
- Produces: `activity_connection_health(events_path: Path, now: datetime, stale_after_seconds: int = 900) -> str`
- Extends: `OverlayViewModel` with `activity_stale: bool`
- Consumes: existing activity file metadata only; do not read prompts/commands.

- [ ] **Step 1: Write failing freshness tests**

Add tests for fresh, stale, and missing `activity-events.jsonl` states.

- [ ] **Step 2: Run tests to verify failure**

Run target app integration and activity tests.

- [ ] **Step 3: Implement freshness detection**

Use file modified time and event availability to set health text such as `状态连接陈旧，请修复`.

- [ ] **Step 4: Update overlay panel actions**

When stale, show a clear repair button in the panel that calls the existing `_repair_companion_integration`.

- [ ] **Step 5: Run target tests**

Expected: target tests pass.

### Task 5: Verification And Docs

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Run full tests**

Run: `$env:PYTHONPATH = (Resolve-Path .\windows); .\.venv\Scripts\python.exe -m unittest discover .\windows\tests -v`

- [ ] **Step 2: Run GUI smoke**

Run: `$env:PYTHONPATH = (Resolve-Path .\windows); .\.venv\Scripts\python.exe .\windows\tools\app_smoke.py --duration 3`

- [ ] **Step 3: Update README progress**

Add a dated progress line for UI polish, topmost toggle, smooth icon rendering, and stale activity health.

- [ ] **Step 4: Review diff**

Run: `git diff --stat` and `git diff`.
