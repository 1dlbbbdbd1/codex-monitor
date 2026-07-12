# Codex Floating Companion v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and package a Windows v0.1 Demo that shows Codex quota/reset windows and all-task activity through a draggable, edge-docking floating companion with attention badges.

**Architecture:** Import the Windows implementation of `ademisler/codexcontrol` as the quota/account baseline, then add isolated activity ingestion, projection, notification, hook-installation, geometry, overlay, and navigation modules. Codex hooks append privacy-minimized JSONL events; the desktop process incrementally projects them and renders a Tk floating overlay while the existing quota dashboard remains available.

**Tech Stack:** Python 3.11+, tkinter, pystray, Pillow, Requests, unittest, PowerShell, PyInstaller, Codex hooks JSON, Win32 APIs through ctypes.

## Global Constraints

- Target Windows 10 and Windows 11 on x64.
- Keep the existing CodexControl quota/auth implementation behavior-preserving.
- Do not require an OpenAI API key or send model requests.
- Do not store prompts, responses, commands, diffs, environment variables, or auth tokens in activity events.
- Store companion data under `%APPDATA%\CodexFloatingCompanion`.
- Aggregate status precedence is `waitingApproval > failed > working > completed > idle > unknown`.
- Approval badges clear only after resolution or terminal task state; completion/failure/quota-reset badges clear after the panel is viewed.
- Never auto-approve or auto-deny a Codex request.
- Preserve the upstream MIT license and attribution.
- Use TDD for every behavior change and commit after each independently testable task.

---

## File Structure

### Imported and modified

- `windows/CodexControlWindows.pyw`: preserve GUI entry point and add hook-emission CLI dispatch before GUI startup.
- `windows/codexcontrol_windows/app.py`: compose new services and overlay; do not place new domain logic here.
- `windows/codexcontrol_windows/file_locations.py`: expose companion activity, settings, log, and hook-backup paths.
- `windows/codexcontrol_windows/models.py`: retain quota/account models unchanged except shared serialization helpers if required.
- `windows/install.ps1`: install executable, startup shortcut, hooks integration, and plugin bundle.
- `windows/package_release.ps1`: package executable, plugin, license, checksum, and release notes.
- `windows/build.ps1`: include new modules and plugin assets in the PyInstaller build.
- `README.md`: user installation, privacy, known limitations, and upstream attribution.

### New focused modules

- `windows/codexcontrol_windows/activity_models.py`: event, task projection, connection health, and aggregate view types.
- `windows/codexcontrol_windows/activity_store.py`: atomic JSONL append, incremental reader, event validation, deduplication, projection, and snapshot persistence.
- `windows/codexcontrol_windows/notification_state.py`: unread attention state and acknowledgement rules.
- `windows/codexcontrol_windows/bridge_cli.py`: parse sanitized hook payload and append one event without launching the GUI.
- `windows/codexcontrol_windows/hook_installer.py`: merge, upgrade, back up, and remove companion-owned hooks.
- `windows/codexcontrol_windows/settings_store.py`: overlay position and behavior persistence.
- `windows/codexcontrol_windows/overlay_geometry.py`: pure DPI-aware docking, hiding, and monitor recovery calculations.
- `windows/codexcontrol_windows/floating_overlay.py`: Tk top-level overlay and compact task/quota panel.
- `windows/codexcontrol_windows/codex_navigation.py`: precise task navigation when supported and safe foreground fallback.
- `plugin/codex-floating-companion/.codex-plugin/plugin.json`: plugin metadata and future-compatible hook declaration.
- `plugin/codex-floating-companion/hooks/hooks.json`: companion-tagged hook templates.
- `plugin/codex-floating-companion/skills/companion-status/SKILL.md`: explain status health and repair workflow inside Codex.

### New tests

- `windows/tests/test_activity_models.py`
- `windows/tests/test_activity_store.py`
- `windows/tests/test_notification_state.py`
- `windows/tests/test_bridge_cli.py`
- `windows/tests/test_hook_installer.py`
- `windows/tests/test_settings_store.py`
- `windows/tests/test_overlay_geometry.py`
- `windows/tests/test_codex_navigation.py`
- `windows/tests/test_app_integration.py`

---

### Task 1: Import and verify the upstream baseline

**Files:**
- Import: `.github/`, `Scripts/`, `Sources/`, `Support/`, `Tests/`, `windows/`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`, `Package.swift`, `SECURITY.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: upstream branch `ademisler/codexcontrol:main` at the fetched commit.
- Produces: an unchanged, testable Windows baseline plus an `upstream` Git remote.

- [ ] **Step 1: Add and fetch the upstream remote**

```powershell
git remote add upstream https://github.com/ademisler/codexcontrol.git
git fetch upstream main
git rev-parse upstream/main
```

Expected: a 40-character commit SHA and no modification of the working tree.

- [ ] **Step 2: Import the exact upstream paths without replacing project docs**

```powershell
git checkout upstream/main -- .github Scripts Sources Support Tests windows CHANGELOG.md CONTRIBUTING.md LICENSE Package.swift SECURITY.md
git status --short
```

Expected: imported paths are staged; `README.md` and `docs/` remain from this repository.

- [ ] **Step 3: Record source provenance in README**

Add this exact section:

```markdown
## Upstream

The quota/account foundation is derived from [ademisler/codexcontrol](https://github.com/ademisler/codexcontrol) under the MIT License. The imported source commit is recorded in Git history and `UPSTREAM.md`.
```

Create `UPSTREAM.md` with repository URL, imported SHA from Step 1, import date `2026-07-12`, license `MIT`, and update procedure `git fetch upstream main`.

- [ ] **Step 4: Run the baseline Windows tests**

```powershell
$env:PYTHONPATH = (Resolve-Path .\windows)
python -m unittest discover .\windows\tests -v
```

Expected: all imported Windows tests pass before feature changes.

- [ ] **Step 5: Commit the baseline**

```powershell
git add .
git commit -m "chore: import CodexControl upstream baseline"
```

---

### Task 2: Define activity events, task states, and aggregation

**Files:**
- Create: `windows/codexcontrol_windows/activity_models.py`
- Test: `windows/tests/test_activity_models.py`

**Interfaces:**
- Produces: `ActivityEvent.from_dict(payload)`, `TaskProjection.apply(event)`, `aggregate_tasks(tasks) -> AggregateStatus`.
- Consumes: UTC ISO-8601 helpers from `models.py` only.

- [ ] **Step 1: Write failing model and aggregation tests**

```python
def test_waiting_approval_has_highest_priority():
    tasks = [task("a", "working"), task("b", "waitingApproval"), task("c", "failed")]
    aggregate = aggregate_tasks(tasks)
    assert aggregate.status is ActivityStatus.WAITING_APPROVAL
    assert aggregate.attention_count == 1


def test_event_rejects_sensitive_or_oversized_fields():
    with self.assertRaises(ActivityValidationError):
        ActivityEvent.from_dict({"schemaVersion": 1, "eventType": "turn_started", "prompt": "secret"})
```

- [ ] **Step 2: Run tests and confirm RED**

```powershell
$env:PYTHONPATH = (Resolve-Path .\windows)
python -m unittest windows.tests.test_activity_models -v
```

Expected: import failure for `activity_models`.

- [ ] **Step 3: Implement the minimal domain types**

```python
class ActivityStatus(str, Enum):
    UNKNOWN = "unknown"
    IDLE = "idle"
    WORKING = "working"
    WAITING_APPROVAL = "waitingApproval"
    COMPLETED = "completed"
    FAILED = "failed"


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


def aggregate_tasks(tasks: Iterable[TaskProjection]) -> AggregateStatus:
    priority = {
        ActivityStatus.WAITING_APPROVAL: 0,
        ActivityStatus.FAILED: 1,
        ActivityStatus.WORKING: 2,
        ActivityStatus.COMPLETED: 3,
        ActivityStatus.IDLE: 4,
        ActivityStatus.UNKNOWN: 5,
    }
    materialized = list(tasks)
    selected = min((task.status for task in materialized), key=priority.get, default=ActivityStatus.IDLE)
    return AggregateStatus(
        status=selected,
        working_count=sum(task.status is ActivityStatus.WORKING for task in materialized),
        attention_count=sum(task.status is ActivityStatus.WAITING_APPROVAL for task in materialized),
    )
```

- [ ] **Step 4: Run model tests and full baseline tests**

Expected: new tests and all upstream tests pass.

- [ ] **Step 5: Commit**

```powershell
git add windows/codexcontrol_windows/activity_models.py windows/tests/test_activity_models.py
git commit -m "feat: model Codex activity states"
```

---

### Task 3: Build the append-only event bridge and incremental projection store

**Files:**
- Create: `windows/codexcontrol_windows/activity_store.py`
- Modify: `windows/codexcontrol_windows/file_locations.py`
- Test: `windows/tests/test_activity_store.py`

**Interfaces:**
- Consumes: `ActivityEvent`, `TaskProjection`.
- Produces: `append_event(path, event)`, `ActivityStore.poll() -> ActivitySnapshot`, `ActivityStore.save()`.

- [ ] **Step 1: Write failing tests for append, half-line recovery, bad-line isolation, and deduplication**

```python
def test_poll_keeps_offset_before_incomplete_tail(self):
    events.write_bytes(valid_event + b"\n{\"schemaVersion\":1")
    first = store.poll()
    self.assertEqual(len(first.tasks), 1)
    events.write_bytes(events.read_bytes() + remainder)
    second = store.poll()
    self.assertEqual(len(second.tasks), 2)


def test_duplicate_event_id_is_applied_once(self):
    append_event(events, event)
    append_event(events, event)
    self.assertEqual(store.poll().applied_event_count, 1)
```

- [ ] **Step 2: Run targeted tests and confirm RED**

Expected: import failure for `activity_store`.

- [ ] **Step 3: Implement atomic append and incremental reader**

Use `os.open(..., os.O_APPEND | os.O_CREAT | os.O_WRONLY)` and one UTF-8 encoded write per event. Persist:

```python
@dataclass(slots=True)
class ActivityStoreState:
    byte_offset: int = 0
    recent_event_ids: list[str] = field(default_factory=list)
    tasks: dict[str, TaskProjection] = field(default_factory=dict)
```

Cap `recent_event_ids` at 4096 and write snapshots through a temporary file plus `os.replace`.

- [ ] **Step 4: Run targeted and full tests**

Expected: all tests pass and no activity test reads outside its temporary directory.

- [ ] **Step 5: Commit**

```powershell
git add windows/codexcontrol_windows/activity_store.py windows/codexcontrol_windows/file_locations.py windows/tests/test_activity_store.py
git commit -m "feat: persist Codex activity events"
```

---

### Task 4: Implement notification acknowledgement rules

**Files:**
- Create: `windows/codexcontrol_windows/notification_state.py`
- Test: `windows/tests/test_notification_state.py`

**Interfaces:**
- Consumes: task terminal/approval transitions and quota snapshots.
- Produces: `NotificationState.observe_activity(...)`, `observe_quota(...)`, `acknowledge_panel_view()`, `badge`.

- [ ] **Step 1: Write failing tests for persistent approval and view-cleared informational badges**

```python
def test_panel_view_does_not_clear_unresolved_approval(self):
    state.observe_activity(waiting_approval_event)
    state.acknowledge_panel_view()
    self.assertTrue(state.badge.approval)


def test_quota_reset_is_not_reported_on_first_snapshot(self):
    state.observe_quota(snapshot(remaining=5, reset_at=reset))
    self.assertFalse(state.badge.quota_reset)
```

- [ ] **Step 2: Run and confirm RED**

- [ ] **Step 3: Implement immutable badge projection and persisted acknowledgement watermark**

```python
@dataclass(frozen=True, slots=True)
class BadgeState:
    approval: bool = False
    failure: bool = False
    completion: bool = False
    quota_reset: bool = False

    @property
    def visible(self) -> bool:
        return self.approval or self.failure or self.completion or self.quota_reset
```

- [ ] **Step 4: Run targeted and full tests**

- [ ] **Step 5: Commit**

```powershell
git add windows/codexcontrol_windows/notification_state.py windows/tests/test_notification_state.py
git commit -m "feat: track companion attention badges"
```

---

### Task 5: Add the hook bridge CLI and safe hook installer

**Files:**
- Create: `windows/codexcontrol_windows/bridge_cli.py`
- Create: `windows/codexcontrol_windows/hook_installer.py`
- Create: `plugin/codex-floating-companion/.codex-plugin/plugin.json`
- Create: `plugin/codex-floating-companion/hooks/hooks.json`
- Create: `plugin/codex-floating-companion/skills/companion-status/SKILL.md`
- Modify: `windows/CodexControlWindows.pyw`
- Test: `windows/tests/test_bridge_cli.py`
- Test: `windows/tests/test_hook_installer.py`

**Interfaces:**
- Consumes: stdin hook JSON and companion executable path.
- Produces: `bridge_cli.main(argv, stdin) -> int`, `HookInstaller.install(executable)`, `HookInstaller.uninstall()`.

- [ ] **Step 1: Invoke and follow the installed `plugin-creator` skill before scaffolding plugin files**

Read its full `SKILL.md`, generate a valid manifest, and retain global-hook fallback because current plugin-local hook loading is unreliable.

- [ ] **Step 2: Write failing bridge sanitization and hook merge tests**

```python
def test_bridge_ignores_prompt_and_command_fields(self):
    payload = {"type": "PermissionRequest", "thread_id": "t", "prompt": "secret", "command": "rm"}
    event = normalize_hook_payload(payload, now=fixed_now)
    serialized = event.to_dict()
    self.assertNotIn("prompt", serialized)
    self.assertNotIn("command", serialized)


def test_install_preserves_unrelated_hooks_and_is_idempotent(self):
    installer.install(executable)
    installer.install(executable)
    result = json.loads(hooks_path.read_text("utf-8"))
    self.assertEqual(result["hooks"]["Stop"][0]["description"], "existing")
    self.assertEqual(count_companion_hooks(result), expected_companion_hook_count)
```

- [ ] **Step 3: Implement bridge dispatch before Tk initialization**

```python
if "--emit-hook" in sys.argv:
    raise SystemExit(bridge_main(sys.argv[1:], sys.stdin))

app = CodexControlWindowsApp(start_hidden="--hidden" in sys.argv)
app.run()
```

- [ ] **Step 4: Implement backup + atomic merge + targeted uninstall**

Companion entries must include `"description": "codex-floating-companion:<event>"`. Reject malformed existing JSON, write `<hooks>.backup-YYYYMMDD-HHMMSS.json`, then replace atomically.

- [ ] **Step 5: Run plugin validation, targeted tests, and full tests**

Expected: valid manifest; malformed hooks test leaves original file byte-for-byte unchanged.

- [ ] **Step 6: Commit**

```powershell
git add plugin windows/CodexControlWindows.pyw windows/codexcontrol_windows/bridge_cli.py windows/codexcontrol_windows/hook_installer.py windows/tests/test_bridge_cli.py windows/tests/test_hook_installer.py
git commit -m "feat: bridge Codex lifecycle events"
```

---

### Task 6: Persist overlay settings and implement pure docking geometry

**Files:**
- Create: `windows/codexcontrol_windows/settings_store.py`
- Create: `windows/codexcontrol_windows/overlay_geometry.py`
- Test: `windows/tests/test_settings_store.py`
- Test: `windows/tests/test_overlay_geometry.py`

**Interfaces:**
- Produces: `OverlaySettingsStore.load/save`, `dock_target`, `hidden_target`, `recover_to_monitors`.
- Consumes: logical window rectangle, monitor work areas, DPI scale, pointer location.

- [ ] **Step 1: Write failing geometry tests**

```python
def test_right_dock_keeps_twelve_pixel_handle_visible():
    work = Rect(0, 0, 1920, 1040)
    ball = Size(56, 56)
    target = hidden_target(work, ball, DockEdge.RIGHT, handle_px=12)
    self.assertEqual(target.x, 1908)


def test_removed_monitor_recovers_window_to_primary_work_area():
    recovered = recover_to_monitors(saved, [primary])
    self.assertTrue(primary.contains(recovered.visible_handle_rect))
```

- [ ] **Step 2: Run and confirm RED**

- [ ] **Step 3: Implement pure geometry and atomic settings persistence**

Use dataclasses `Rect`, `Size`, `Point`, `Monitor`, `OverlayPlacement`, `DockEdge`. Store monitor device name plus normalized coordinates, never raw coordinates alone.

- [ ] **Step 4: Run targeted and full tests**

- [ ] **Step 5: Commit**

```powershell
git add windows/codexcontrol_windows/settings_store.py windows/codexcontrol_windows/overlay_geometry.py windows/tests/test_settings_store.py windows/tests/test_overlay_geometry.py
git commit -m "feat: add DPI-aware overlay placement"
```

---

### Task 7: Build the floating ball and compact panel

**Files:**
- Create: `windows/codexcontrol_windows/floating_overlay.py`
- Modify: `windows/codexcontrol_windows/brand_icon.py`
- Test: `windows/tests/test_app_integration.py`

**Interfaces:**
- Consumes: `OverlayViewModel`, `OverlaySettingsStore`, callbacks `on_refresh`, `on_task_open`, `on_panel_viewed`.
- Produces: `FloatingOverlay.show/update/hide/destroy` and stable Tk lifecycle.

- [ ] **Step 1: Write failing view-model rendering tests without opening a display**

```python
def test_waiting_approval_view_model_shows_red_badge_and_count():
    model = make_overlay_view_model(aggregate=waiting(count=2), badge=approval_badge())
    self.assertEqual(model.badge_color, "#ef4444")
    self.assertEqual(model.count_text, "2")
    self.assertTrue(model.keep_handle_visible)
```

- [ ] **Step 2: Run and confirm RED**

- [ ] **Step 3: Implement the overlay controller**

Create one transparent borderless `tk.Toplevel`, mark it topmost, draw the ball on Canvas, bind press/drag/release, and schedule animation with `after`. Keep Win32 calls in small helpers for dark mode, DPI awareness, foreground behavior, and rounded hit region.

- [ ] **Step 4: Implement compact panel layout**

Render quota rows, connection health, task rows, manual refresh, settings link, and timestamps. Opening the panel calls `on_panel_viewed` once; closing it re-enables edge-hide timing.

- [ ] **Step 5: Run headless logic tests and a guarded GUI smoke test**

```powershell
$env:PYTHONPATH = (Resolve-Path .\windows)
python -m unittest windows.tests.test_app_integration -v
python .\windows\tools\overlay_smoke.py --duration 5
```

Expected: unit tests pass; smoke window opens for five seconds without traceback when an interactive desktop is available.

- [ ] **Step 6: Commit**

```powershell
git add windows/codexcontrol_windows/floating_overlay.py windows/codexcontrol_windows/brand_icon.py windows/tests/test_app_integration.py windows/tools/overlay_smoke.py
git commit -m "feat: add floating Codex status overlay"
```

---

### Task 8: Integrate activity, quota, navigation, and health into the app

**Files:**
- Create: `windows/codexcontrol_windows/codex_navigation.py`
- Modify: `windows/codexcontrol_windows/app.py`
- Test: `windows/tests/test_codex_navigation.py`
- Test: `windows/tests/test_app_integration.py`

**Interfaces:**
- Consumes: activity snapshots, notification state, current quota snapshot, `FloatingOverlay`.
- Produces: periodic view-model updates and safe task-open behavior.

- [ ] **Step 1: Write failing navigation and composition tests**

```python
def test_open_task_falls_back_to_foreground_without_private_state_edits(self):
    result = navigator.open_task(task, precise_handler=None)
    self.assertEqual(result.mode, NavigationMode.FOREGROUND_FALLBACK)
    foreground.assert_called_once()
    private_state_writer.assert_not_called()
```

- [ ] **Step 2: Run and confirm RED**

- [ ] **Step 3: Implement navigation and app polling**

Poll activity JSONL every 500 ms on the existing Tk event loop, never on the UI thread for disk/network work. Rebuild `OverlayViewModel` only when revisions change. Treat hook freshness and parse errors as explicit `ConnectionHealth` values.

- [ ] **Step 4: Preserve existing dashboard and tray behaviors**

Tray menu gains `Show/Hide Floating Companion`, `Repair Codex Integration`, and existing dashboard/quit actions. Existing account switching and quota refresh remain unchanged.

- [ ] **Step 5: Run all Windows tests**

Expected: all imported and new tests pass.

- [ ] **Step 6: Commit**

```powershell
git add windows/codexcontrol_windows/app.py windows/codexcontrol_windows/codex_navigation.py windows/tests/test_codex_navigation.py windows/tests/test_app_integration.py
git commit -m "feat: integrate quota and activity companion"
```

---

### Task 9: Install, upgrade, uninstall, and package the Demo

**Files:**
- Modify: `windows/build.ps1`
- Modify: `windows/install.ps1`
- Modify: `windows/package_release.ps1`
- Create: `windows/uninstall.ps1`
- Create: `docs/known-limitations.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: built `CodexFloatingCompanion.exe`, plugin directory, hook installer CLI.
- Produces: `CodexFloatingCompanion-v0.1.0-windows-x64.zip` and SHA-256 file.

- [ ] **Step 1: Add a packaging smoke test before script changes**

Add `windows/tests/test_release_layout.py` that validates required ZIP entries from a temporary fixture: executable, `LICENSE`, `UPSTREAM.md`, plugin manifest, install/uninstall scripts, and known limitations.

- [ ] **Step 2: Run and confirm RED**

- [ ] **Step 3: Update build and installer scripts**

Rename the executable to `CodexFloatingCompanion.exe`. Installer steps are: copy files to `%LocalAppData%\Programs\CodexFloatingCompanion`, invoke `--install-hooks`, register startup shortcut only when requested, and launch hidden only when requested. Uninstaller invokes `--uninstall-hooks` before deleting product files and leaves timestamped hook backups.

- [ ] **Step 4: Package release metadata**

Generate:

```text
dist/CodexFloatingCompanion-v0.1.0-windows-x64.zip
dist/CodexFloatingCompanion-v0.1.0-windows-x64.zip.sha256
```

- [ ] **Step 5: Run tests, build, and inspect archive**

```powershell
$env:PYTHONPATH = (Resolve-Path .\windows)
python -m unittest discover .\windows\tests -v
powershell -ExecutionPolicy Bypass -File .\windows\build.ps1 -Clean
powershell -ExecutionPolicy Bypass -File .\windows\package_release.ps1 -Version 0.1.0
```

Expected: all tests pass, executable builds, ZIP and checksum exist, archive includes required files.

- [ ] **Step 6: Commit**

```powershell
git add windows README.md docs/known-limitations.md
git commit -m "build: package v0.1.0 Windows demo"
```

---

### Task 10: Verify the Demo and publish the GitHub repository

**Files:**
- Create: `docs/verification/v0.1.0.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: packaged Demo and Git history.
- Produces: verified `v0.1.0` tag, GitHub repository, pushed commits, and release asset when permissions allow.

- [ ] **Step 1: Run the full automated verification suite from a clean checkout state**

```powershell
git status --short
$env:PYTHONPATH = (Resolve-Path .\windows)
python -m unittest discover .\windows\tests -v
```

Expected: clean status before generated artifacts; all tests pass.

- [ ] **Step 2: Perform Windows interactive smoke checks**

Record evidence for: launch, quota render or explicit auth-needed state, drag, left/right dock, two-second hide, visible red badge fixture, panel open/acknowledge, restart placement restore, and tray exit. Where real Codex approval cannot be safely forced, use the hook bridge fixture and mark real approval verification as a documented limitation rather than claiming it passed.

- [ ] **Step 3: Write verification report and commit**

`docs/verification/v0.1.0.md` must list exact commands, outputs, machine/OS/DPI, passed checks, failed checks, and known limitations.

```powershell
git add README.md docs/verification/v0.1.0.md
git commit -m "docs: record v0.1.0 verification"
```

- [ ] **Step 4: Create the GitHub repository after obtaining user authorization**

Install GitHub CLI if absent, authenticate as the connected user, then:

```powershell
gh repo create codex-floating-companion --public --source . --remote origin --push --description "Windows floating quota and activity companion for OpenAI Codex"
```

Expected: new public repository under the authenticated account and `main` pushed.

- [ ] **Step 5: Tag and publish the Demo**

```powershell
git tag -a v0.1.0 -m "Codex Floating Companion v0.1.0 demo"
git push origin v0.1.0
gh release create v0.1.0 .\windows\dist\CodexFloatingCompanion-v0.1.0-windows-x64.zip .\windows\dist\CodexFloatingCompanion-v0.1.0-windows-x64.zip.sha256 --title "v0.1.0 Demo" --notes-file docs/known-limitations.md
```

Expected: GitHub tag and release show both assets.

---

## Plan Self-Review Results

- Spec coverage: every required quota, activity, badge, docking, navigation, privacy, install, package, and publish requirement maps to at least one task.
- Scope: one Windows Demo; macOS and non-Codex providers remain out of scope.
- Type consistency: event, projection, aggregate, badge, placement, and navigation interfaces are defined before consumers.
- Placeholders: no implementation placeholder is permitted; real approval verification has an explicit fixture fallback and honest limitation rule.
- Commit structure: design, baseline, domain, persistence, notifications, bridge, geometry, overlay, integration, packaging, and verification each have separate commits.
