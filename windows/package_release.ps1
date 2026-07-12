param(
    [switch]$Clean,
    [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$windowsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $windowsRoot
$releaseRoot = Join-Path $repoRoot "outputs"
$packageRoot = Join-Path $releaseRoot "CodexFloatingCompanion-windows-x64"
$zipPath = Join-Path $releaseRoot "CodexFloatingCompanion-windows-x64.zip"
$hashPath = "$zipPath.sha256"
$buildArgs = @()
if ($Clean) { $buildArgs += "-Clean" }
if (-not [string]::IsNullOrWhiteSpace($PythonExecutable)) {
    $buildArgs += @("-PythonExecutable", $PythonExecutable)
}

& powershell -ExecutionPolicy Bypass -File (Join-Path $windowsRoot "build.ps1") @buildArgs
if ($LASTEXITCODE -ne 0) { throw "Windows build failed with exit code $LASTEXITCODE" }
New-Item -ItemType Directory -Force -Path $releaseRoot | Out-Null
Remove-Item -LiteralPath $packageRoot -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $hashPath -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $packageRoot | Out-Null

Copy-Item (Join-Path $windowsRoot "dist\CodexFloatingCompanion.exe") $packageRoot
Copy-Item (Join-Path $windowsRoot "install.ps1") $packageRoot
Copy-Item (Join-Path $windowsRoot "uninstall.ps1") $packageRoot
Copy-Item (Join-Path $windowsRoot "README.md") $packageRoot
Copy-Item (Join-Path $repoRoot "LICENSE") $packageRoot
Copy-Item (Join-Path $repoRoot "docs\known-limitations.md") $packageRoot
$pluginTarget = Join-Path $packageRoot "plugin\codex-floating-companion"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $pluginTarget) | Out-Null
Copy-Item (Join-Path $repoRoot "plugin\codex-floating-companion") $pluginTarget -Recurse

Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal
$hash = (Get-FileHash -Algorithm SHA256 $zipPath).Hash.ToLowerInvariant()
Set-Content -LiteralPath $hashPath -Value "$hash  CodexFloatingCompanion-windows-x64.zip" -Encoding ascii
Write-Output $zipPath
Write-Output $hashPath
