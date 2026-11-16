# ==============================================================================
# OPERATION JARVIS — Workstation Quick-Start Script (JARVIS-START.ps1)
# ==============================================================================
# Idempotent, robust startup for Ollama (11434) and Operation JARVIS Backend (8000).
# Keeps services hidden in background, verifies health, and displays status.
# ==============================================================================

$ErrorActionPreference = "Continue"

$root = "C:\Users\Akshay aravind .rv\operation_jarvis"
$logsDir = Join-Path $root "logs"
$startupLog = Join-Path $logsDir "startup.log"

if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

function Log-Startup([string]$msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $startupLog -Value "[$timestamp] $msg"
}

Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "           OPERATION JARVIS -- WORKSTATION START       " -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Log-Startup "Initiating JARVIS startup sequence."

# --- STEP 1: Check and Start Ollama ---
Write-Host "[1/4] Checking Ollama Service (Port 11434)..." -NoNewline
$ollamaListening = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue

if (-not $ollamaListening) {
    Write-Host " Starting..." -ForegroundColor Yellow
    Log-Startup "Ollama not running. Starting background process."
    $ollamaExe = (Get-Command "ollama" -ErrorAction SilentlyContinue).Source
    if (-not $ollamaExe -or -not (Test-Path $ollamaExe)) {
        $ollamaExe = "C:\Users\Akshay aravind .rv\AppData\Local\Programs\Ollama\ollama.exe"
    }
    $ollamaCmd = "`"$ollamaExe`" serve"
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = $ollamaCmd
        CurrentDirectory = $root
    } | Out-Null
} else {
    Write-Host " Already running." -ForegroundColor Green
}

# Verify Ollama API responsiveness
$ollamaReady = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($resp) {
            $ollamaReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $ollamaReady) {
    Write-Host "`n[FAILED] Ollama did not respond on port 11434 within 30 seconds." -ForegroundColor Red
    Log-Startup "ERROR: Ollama port 11434 health check failed."
    Read-Host "Press Enter to exit..."
    exit 1
}
Write-Host "      [OK] Ollama API is responsive." -ForegroundColor Green

# --- STEP 2: Check and Start JARVIS FastAPI Backend ---
Write-Host "[2/4] Checking JARVIS Backend (Port 8000)..." -NoNewline
$jarvisListening = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

if (-not $jarvisListening) {
    Write-Host " Starting..." -ForegroundColor Yellow
    Log-Startup "JARVIS backend not running. Starting uvicorn daemon."
    $pythonExe = Join-Path $root ".venv\Scripts\python.exe"
    
    if (-not (Test-Path $pythonExe)) {
        Write-Host "`n[FAILED] Python virtual environment not found at $pythonExe" -ForegroundColor Red
        Log-Startup "ERROR: Python virtual environment missing."
        Read-Host "Press Enter to exit..."
        exit 1
    }

    $uvicornCmd = "`"$pythonExe`" -m uvicorn api.app:app --host 127.0.0.1 --port 8000"
    Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
        CommandLine = $uvicornCmd
        CurrentDirectory = $root
    } | Out-Null
} else {
    Write-Host " Already running." -ForegroundColor Green
}

# Verify Backend responsiveness
$backendReady = $false
for ($i = 1; $i -le 30; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/dashboard/summary" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($resp -and ($resp.status -or $resp.ok)) {
            $backendReady = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $backendReady) {
    try {
        $docsResp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/docs" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($docsResp.StatusCode -eq 200) {
            $backendReady = $true
        }
    } catch {}
}

if (-not $backendReady) {
    Write-Host "`n[FAILED] JARVIS Backend did not respond on port 8000 within 30 seconds." -ForegroundColor Red
    Log-Startup "ERROR: Backend port 8000 health check failed."
    Read-Host "Press Enter to exit..."
    exit 1
}
Write-Host "      [OK] Backend API is responsive." -ForegroundColor Green

# --- STEP 3: Verify Tailscale Serve ---
Write-Host "[3/4] Verifying Tailscale Serve Ingress..." -NoNewline
$tailscaleBin = "tailscale"
if (-not (Get-Command $tailscaleBin -ErrorAction SilentlyContinue)) {
    if (Test-Path "C:\Program Files\Tailscale\tailscale.exe") {
        $tailscaleBin = "C:\Program Files\Tailscale\tailscale.exe"
    }
}

$tailscaleNode = ""
if (Get-Command $tailscaleBin -ErrorAction SilentlyContinue) {
    try {
        $tsRaw = & $tailscaleBin status --json 2>&1
        $tsStatus = $tsRaw | ConvertFrom-Json
        if ($tsStatus -and $tsStatus.Self) {
            $tailscaleNode = $tsStatus.Self.DNSName.TrimEnd(".")
        }
    } catch {}

    $serveRaw = & $tailscaleBin serve status 2>&1
    $serveActive = ($serveRaw -match "8000" -or $serveRaw -match "https://")

    if ($serveActive) {
        Write-Host " Active." -ForegroundColor Green
    } else {
        Write-Host " Configuring..." -ForegroundColor Yellow
        Log-Startup "Tailscale Serve inactive. Executing setup_tailscale_serve.ps1"
        $setupScript = Join-Path $root "scripts\setup_tailscale_serve.ps1"
        Start-Process powershell.exe -ArgumentList "-ExecutionPolicy Bypass -File `"$setupScript`"" -Wait -WindowStyle Hidden
        Write-Host "      [OK] Tailscale Serve configured." -ForegroundColor Green
    }
} else {
    Write-Host " Skipped (Tailscale CLI not installed)." -ForegroundColor Yellow
}

# --- STEP 4: Status Display ---
Write-Host "[4/4] Finalizing Online Diagnostics..." -ForegroundColor Cyan
Write-Host "`n======================================================" -ForegroundColor Green
Write-Host "              [ONLINE] JARVIS WORKSTATION IS READY    " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host "  * Local Host     : http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  * Dashboard      : http://127.0.0.1:8000/dashboard/" -ForegroundColor White
Write-Host "  * Mobile PWA     : http://127.0.0.1:8000/pwa/" -ForegroundColor White
if ($tailscaleNode) {
    Write-Host "  * Tailscale Mesh : https://$tailscaleNode/pwa/" -ForegroundColor Yellow
}
Write-Host "  * Model Persona  : Qwen 3.5 9B (Local-First)" -ForegroundColor White
Write-Host "  * Status         : ALL SYSTEMS OPERATIONAL" -ForegroundColor Green
Write-Host "======================================================`n" -ForegroundColor Green
Log-Startup "JARVIS startup completed successfully."

Start-Sleep -Seconds 2
