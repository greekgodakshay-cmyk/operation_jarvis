# PowerShell Startup Script for Operation Jarvis Agent Runtime
$ErrorActionPreference = "Continue"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$VenvPython = Join-Path $ProjectDir ".venv\Scripts\python.exe"
$PidFile = Join-Path $ProjectDir "data\jarvis_server.pid"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "STARTING OPERATION JARVIS — LOCAL AGENT RUNTIME" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Check Ollama Service
Write-Host "[1/3] Checking Ollama Service..." -ForegroundColor Yellow
$ollamaListening = $false
try {
    $tcp = Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -WarningAction SilentlyContinue
    $ollamaListening = $tcp.TcpTestSucceeded
} catch {
    $ollamaListening = $false
}

if (-not $ollamaListening) {
    Write-Host "Ollama not responding. Starting ollama serve in background..." -ForegroundColor Yellow
    $ollamaProcess = Start-Process -FilePath "ollama" -ArgumentList "serve" -PassThru -NoNewWindow
    Start-Sleep -Seconds 3
} else {
    Write-Host "Ollama is online and listening on 127.0.0.1:11434." -ForegroundColor Green
}

# 2. Check Python Environment
Write-Host "[2/3] Checking Agent Runtime Environment..." -ForegroundColor Yellow
if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found at $VenvPython. Run uv venv first."
    exit 1
}

# 3. Start FastAPI Server
Write-Host "[3/3] Launching FastAPI Agent Server (Port 8000)..." -ForegroundColor Yellow
$serverProcess = Start-Process -FilePath $VenvPython -ArgumentList "-m uvicorn api.app:app --host 127.0.0.1 --port 8000" -WorkingDirectory $ProjectDir -PassThru -NoNewWindow

if ($serverProcess -and -not $serverProcess.HasExited) {
    $serverProcess.Id | Out-File -FilePath $PidFile -Encoding ascii
    Write-Host "FastAPI Agent Server successfully started with PID: $($serverProcess.Id)" -ForegroundColor Green
    Write-Host "API Endpoint:   http://127.0.0.1:8000" -ForegroundColor Cyan
    Write-Host "API Docs:       http://127.0.0.1:8000/docs" -ForegroundColor Cyan
    Write-Host "Health Check:   http://127.0.0.1:8000/api/v1/health" -ForegroundColor Cyan
} else {
    Write-Host "Failed to launch Agent Server process." -ForegroundColor Red
}

Write-Host "============================================================" -ForegroundColor Cyan
