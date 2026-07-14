param(
    [string]$SourceExe = "",
    [switch]$EnableStartup = $true,
    [switch]$Launch
)

$ErrorActionPreference = "Stop"
$windowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($SourceExe)) {
    $SourceExe = Join-Path $windowsRoot "dist\CodexFloatingCompanion.exe"
}
if (-not (Test-Path -LiteralPath $SourceExe)) {
    throw "EXE not found: $SourceExe"
}

$installDir = Join-Path $env:LOCALAPPDATA "Programs\CodexFloatingCompanion"
$installedExe = Join-Path $installDir "CodexFloatingCompanion.exe"
$startupDir = [Environment]::GetFolderPath("Startup")
$startupShortcut = Join-Path $startupDir "CodexFloatingCompanion.lnk"

Get-Process -Name "CodexFloatingCompanion" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
Copy-Item -LiteralPath $SourceExe -Destination $installedExe -Force

& $installedExe --install-hooks
$hooksPath = Join-Path $env:USERPROFILE ".codex\hooks.json"
$jsonExecutable = $installedExe.Replace("\", "\\")
$hookText = ""
$handlerCount = 0
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $hookText = if (Test-Path -LiteralPath $hooksPath) {
        Get-Content -LiteralPath $hooksPath -Raw -Encoding UTF8
    } else {
        ""
    }
    $handlerCount = ([regex]::Matches($hookText, [regex]::Escape("Codex Floating Companion"))).Count
    if ($handlerCount -eq 4 -and $hookText -match [regex]::Escape($jsonExecutable)) {
        break
    }
    Start-Sleep -Milliseconds 150
}
if ($handlerCount -ne 4 -or $hookText -notmatch [regex]::Escape($jsonExecutable)) {
    throw "Codex hooks installation did not produce four companion handlers."
}

if ($EnableStartup) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($startupShortcut)
    $shortcut.TargetPath = $installedExe
    $shortcut.Arguments = "--hidden"
    $shortcut.WorkingDirectory = $installDir
    $shortcut.IconLocation = $installedExe
    $shortcut.Description = "Launch Codex Floating Companion at sign-in"
    $shortcut.Save()
} elseif (Test-Path -LiteralPath $startupShortcut) {
    Remove-Item -LiteralPath $startupShortcut -Force
}

if ($Launch) {
    Start-Process -FilePath $installedExe -ArgumentList "--hidden" -WorkingDirectory $installDir -WindowStyle Hidden
}

Write-Output "Installed: $installedExe"
Write-Output "Codex activity hooks: installed"
