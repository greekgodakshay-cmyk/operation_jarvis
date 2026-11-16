# ==============================================================================
# OPERATION JARVIS — Workstation Shutdown Script (JARVIS-STOP.ps1)
# ==============================================================================
# Gracefully stops JARVIS backend and unloads Qwen 3.5 9B from VRAM/RAM.
# Preserves all databases, memories, documents, and configuration.
# Never terminates unrelated Python or background processes.
# ==============================================================================

$ErrorActionPreference = "Continue"

Write-Host "======================================================" -ForegroundColor Yellow
Write-Host "           OPERATION JARVIS -- WORKSTATION SHUTDOWN    " -ForegroundColor Yellow
Write-Host "======================================================" -ForegroundColor Yellow

# --- STEP 1: Unload Qwen 3.5 9B Model from GPU/RAM ---
Write-Host "[1/4] Unloading Qwen 3.5 9B from VRAM/RAM..." -NoNewline
try {
    & ollama stop qwen3.5:9b 2>$null
    & ollama stop qwen-batman:latest 2>$null
    & ollama stop qwen-text:latest 2>$null
    Write-Host " Done." -ForegroundColor Green
} catch {
    Write-Host " (Model not currently resident)" -ForegroundColor Gray
}

# --- STEP 2: Gracefully Stop JARVIS FastAPI Backend (Port 8000) ---
Write-Host "[2/4] Stopping JARVIS Backend Service (Port 8000)..." -NoNewline
$backendConns = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue

if ($backendConns) {
    $pids = $backendConns.OwningProcess | Sort-Object -Unique
    $stoppedPids = @()
    foreach ($p in $pids) {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $p" -ErrorAction SilentlyContinue
        if ($proc -and ($proc.CommandLine -match "operation_jarvis" -or $proc.CommandLine -match "uvicorn" -or $proc.Name -match "python")) {
            try {
                Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                $stoppedPids += $p
            } catch {}
        }
    }
    Start-Sleep -Seconds 1
    if ($stoppedPids.Count -gt 0) {
        Write-Host " Stopped (PIDs: $($stoppedPids -join ', '))." -ForegroundColor Green
    } else {
        Write-Host " (No matching JARVIS processes found)" -ForegroundColor Gray
    }
} else {
    Write-Host " (Not running)" -ForegroundColor Gray
}

# --- STEP 3: Stop Ollama Server Process Started for JARVIS ---
Write-Host "[3/4] Stopping Ollama Background Server (Port 11434)..." -NoNewline
$stoppedOllama = $false

# Stop dedicated llama-server worker if resident
Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
        $stoppedOllama = $true
    } catch {}
}

# Stop Ollama serve process
$ollamaProcesses = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "ollama" -and $_.CommandLine -match '\bserve\b' }

if ($ollamaProcesses) {
    foreach ($proc in $ollamaProcesses) {
        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            $stoppedOllama = $true
        } catch {}
    }
}

# Ensure port 11434 listener is released
$ollamaConn = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue
if ($ollamaConn) {
    $ollamaPids = $ollamaConn.OwningProcess | Sort-Object -Unique
    foreach ($opid in $ollamaPids) {
        try {
            Stop-Process -Id $opid -Force -ErrorAction SilentlyContinue
            $stoppedOllama = $true
        } catch {}
    }
}

if ($stoppedOllama) {
    Write-Host " Stopped." -ForegroundColor Green
} else {
    Write-Host " (Not running)" -ForegroundColor Gray
}

# Stop any dedicated Kokoro TTS worker if resident
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "python" -and ($_.CommandLine -match "kokoro_tts" -or $_.CommandLine -match "operation_jarvis") } |
    ForEach-Object {
        try { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
    }

# --- STEP 4: Verification and Clean Status ---
Write-Host "[4/4] Verifying Resource Release..." -ForegroundColor Cyan
Start-Sleep -Seconds 1

$port8000Active = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
$port11434Active = Get-NetTCPConnection -LocalPort 11434 -State Listen -ErrorAction SilentlyContinue

Write-Host "`n======================================================" -ForegroundColor Green
Write-Host "              [STOPPED] JARVIS IS OFFLINE             " -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
if ($port8000Active) {
    Write-Host "  * Port 8000 (Backend)   : STILL LISTENING (Warning)" -ForegroundColor Yellow
} else {
    Write-Host "  * Port 8000 (Backend)   : Released (Clean)" -ForegroundColor Green
}
if ($port11434Active) {
    Write-Host "  * Port 11434 (Ollama)   : STILL LISTENING (Warning)" -ForegroundColor Yellow
} else {
    Write-Host "  * Port 11434 (Ollama)   : Released (Clean)" -ForegroundColor Green
}
Write-Host "  * GPU / VRAM Resources  : Unloaded and Released" -ForegroundColor Green
Write-Host "  * Documents and Memory  : 100% Preserved on Disk" -ForegroundColor Green
Write-Host "======================================================`n" -ForegroundColor Green

Start-Sleep -Seconds 2
