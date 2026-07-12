param(
    [switch]$KeepLocalData
)

$ErrorActionPreference = "Stop"
$installDir = Join-Path $env:LOCALAPPDATA "Programs\CodexFloatingCompanion"
$installedExe = Join-Path $installDir "CodexFloatingCompanion.exe"
$startupShortcut = Join-Path ([Environment]::GetFolderPath("Startup")) "CodexFloatingCompanion.lnk"

Get-Process -Name "CodexFloatingCompanion" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300
if (Test-Path -LiteralPath $installedExe) {
    & $installedExe --uninstall-hooks
    if ($LASTEXITCODE -ne 0) {
        throw "Codex hooks uninstall failed; application files were not removed."
    }
}
if (Test-Path -LiteralPath $startupShortcut) {
    Remove-Item -LiteralPath $startupShortcut -Force
}
if (Test-Path -LiteralPath $installDir) {
    Remove-Item -LiteralPath $installDir -Recurse -Force
}
if (-not $KeepLocalData) {
    $dataDir = Join-Path $env:APPDATA "CodexFloatingCompanion"
    if (Test-Path -LiteralPath $dataDir) {
        Remove-Item -LiteralPath $dataDir -Recurse -Force
    }
}

Write-Output "Codex Floating Companion removed."
