param(
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$flutterAppDir = Join-Path $repoRoot "flutter_app"

$runningApp = Get-Process -Name "flutter_app" -ErrorAction SilentlyContinue
if ($runningApp) {
    Write-Host "Stopping flutter_app.exe before rebuild..."
    $runningApp | Stop-Process -Force
    Start-Sleep -Seconds 2
}

Push-Location $flutterAppDir
try {
    if (-not $SkipClean) {
        Write-Host "Running flutter clean..."
        flutter clean
    }

    Write-Host "Fetching Flutter packages..."
    flutter pub get

    Write-Host "Launching Flutter Windows app..."
    flutter run -d windows
}
finally {
    Pop-Location
}
