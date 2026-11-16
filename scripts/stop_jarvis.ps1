# PowerShell Shutdown Script for Operation Jarvis Agent Runtime
$ErrorActionPreference = "SilentlyContinue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PidFile = Join-Path $ProjectDir "data\jarvis_server.pid"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "STOPPING OPERATION JARVIS AGENT SERVER" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (Test-Path $PidFile) {
    $pidToKill = Get-Content $PidFile
    if ($pidToKill) {
        Write-Host "Stopping Jarvis server process ID: $pidToKill..." -ForegroundColor Yellow
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        Remove-Item -Path $PidFile -Force -ErrorAction SilentlyContinue
        Write-Host "Jarvis Agent Server stopped." -ForegroundColor Green
    }
} else {
    Write-Host "No PID file found. Checking for uvicorn processes on port 8000..." -ForegroundColor Yellow
    Get-Process -Name "*python*" | Where-Object { $_.CommandLine -like "*api.app:app*" } | Stop-Process -Force
    Write-Host "Cleared running instances." -ForegroundColor Green
}

Write-Host "============================================================" -ForegroundColor Cyan
