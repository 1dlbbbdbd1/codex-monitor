# Codex Floating Companion for Windows

## Run and test

```powershell
$env:PYTHONPATH = (Resolve-Path .\windows)
.\.venv\Scripts\python.exe .\windows\CodexControlWindows.pyw
.\.venv\Scripts\python.exe -m unittest discover .\windows\tests -v
```

## Build and package

```powershell
powershell -ExecutionPolicy Bypass -File .\windows\package_release.ps1 -Clean -PythonExecutable .\.venv\Scripts\python.exe
```

Outputs are written to `outputs\CodexFloatingCompanion-windows-x64.zip` with a SHA-256 sidecar.

## Runtime data

- Quota/account data: `%APPDATA%\CodexControl`
- Companion activity/settings: `%APPDATA%\CodexFloatingCompanion`
- Codex integration: `%USERPROFILE%\.codex\hooks.json`

The hook installer makes a timestamped backup before changing an existing hooks file and removes only handlers owned by this companion during uninstall.
