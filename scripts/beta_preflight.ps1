$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$SmokeToken = if ($env:BETA_SMOKE_TOKEN) { $env:BETA_SMOKE_TOKEN } else { "beta-preflight-token" }

Write-Host "[beta-preflight] backend compile"
Set-Location "$RootDir\backend"
& $PythonBin -m compileall app tests scripts

Write-Host "[beta-preflight] backend tests"
& $PythonBin -m unittest discover -s tests -v

Write-Host "[beta-preflight] app boot smoke"
& $PythonBin -m unittest tests.test_app_boot -v

Write-Host "[beta-preflight] process + websocket smoke"
& $PythonBin scripts/process_smoke_check.py --token $SmokeToken

Write-Host "[beta-preflight] flutter analyze"
Set-Location "$RootDir\flutter_app"
flutter analyze

Write-Host "[beta-preflight] cloud functions tests"
Set-Location "$RootDir\cloud_functions"
npm test

Write-Host "[beta-preflight] complete"
