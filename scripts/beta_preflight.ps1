$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "py" }
$PythonArgs = if ($env:PYTHON_BIN) { @() } else { @("-3.11") }
$SmokeToken = if ($env:BETA_SMOKE_TOKEN) { $env:BETA_SMOKE_TOKEN } else { "beta-preflight-token" }

function Invoke-Python {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    & $PythonBin @PythonArgs @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE"
    }
}

Write-Host "[beta-preflight] backend compile"
Set-Location $RootDir
Invoke-Python -m compileall backend\app backend\tests backend\scripts

Write-Host "[beta-preflight] backend tests"
Invoke-Python -m unittest discover -s backend\tests -v

Write-Host "[beta-preflight] app boot smoke"
Invoke-Python -m unittest discover -s backend\tests -p test_app_boot.py -v

Write-Host "[beta-preflight] process + websocket smoke"
Invoke-Python backend\scripts\process_smoke_check.py --token $SmokeToken

Write-Host "[beta-preflight] flutter analyze"
Set-Location "$RootDir\flutter_app"
flutter analyze

Write-Host "[beta-preflight] cloud functions tests"
Set-Location "$RootDir\cloud_functions"
npm test

Write-Host "[beta-preflight] complete"
