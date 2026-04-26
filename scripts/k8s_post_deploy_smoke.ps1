param(
    [Parameter(Mandatory = $true)][string]$Namespace,
    [Parameter(Mandatory = $true)][string]$Deployment,
    [Parameter(Mandatory = $true)][string]$Service,
    [Parameter(Mandatory = $true)][string]$Token,
    [string]$Context = ""
)

$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$RemotePort = if ($env:K8S_SMOKE_REMOTE_PORT) { $env:K8S_SMOKE_REMOTE_PORT } else { "80" }
$TimeoutSeconds = if ($env:K8S_SMOKE_TIMEOUT) { $env:K8S_SMOKE_TIMEOUT } else { "180" }

Set-Location $RootDir
& $PythonBin scripts\k8s_post_deploy_smoke.py `
    --namespace $Namespace `
    --deployment $Deployment `
    --service $Service `
    --token $Token `
    --remote-port $RemotePort `
    --timeout-seconds $TimeoutSeconds `
    --context $Context
