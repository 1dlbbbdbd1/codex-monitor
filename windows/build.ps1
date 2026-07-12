param(
    [switch]$Clean,
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"

$windowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $windowsRoot
Set-Location $repoRoot

$pythonLauncherArgs = @()
if (-not [string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $pythonExecutable = (Resolve-Path -LiteralPath $PythonExecutable).Path
} elseif (Test-Path -LiteralPath (Join-Path $repoRoot ".venv\Scripts\python.exe")) {
    $pythonExecutable = Join-Path $repoRoot ".venv\Scripts\python.exe"
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $pythonExecutable = $pythonCommand.Source
    } else {
        $pyCommand = Get-Command py -ErrorAction SilentlyContinue
        if (-not $pyCommand) {
            throw "Python was not found. Create .venv or pass -PythonExecutable."
        }
        $pythonExecutable = $pyCommand.Source
        $pythonLauncherArgs = @("-3")
    }
}

if ($Clean) {
    Remove-Item -LiteralPath (Join-Path $windowsRoot "build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath (Join-Path $windowsRoot "dist") -Recurse -Force -ErrorAction SilentlyContinue
}

& $pythonExecutable @pythonLauncherArgs -m pip install -r (Join-Path $windowsRoot "requirements-build.txt")
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed with exit code $LASTEXITCODE" }
& $pythonExecutable @pythonLauncherArgs (Join-Path $windowsRoot "tools\generate_app_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Icon generation failed with exit code $LASTEXITCODE" }

$distDir = Join-Path $windowsRoot "dist"
$workDir = Join-Path $windowsRoot "build"
$specDir = $windowsRoot
$iconPath = Join-Path $windowsRoot "build-assets\CodexControl.ico"
$entryPath = Join-Path $windowsRoot "CodexControlWindows.pyw"

& $pythonExecutable @pythonLauncherArgs -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name CodexFloatingCompanion `
  --distpath $distDir `
  --workpath $workDir `
  --specpath $specDir `
  --paths $windowsRoot `
  --icon $iconPath `
  --hidden-import tkinter `
  --hidden-import tkinter.font `
  --hidden-import tkinter.ttk `
  --hidden-import pystray._win32 `
  --hidden-import PIL._tkinter_finder `
  $entryPath
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

Write-Output "Built: $(Join-Path $distDir 'CodexFloatingCompanion.exe')"
