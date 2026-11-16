# Operation JARVIS — Tailscale Serve Secure Remote Access Setup
# HP Victus 15-fa2382TX Host Architecture

Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "  OPERATION JARVIS — TAILSCALE SERVE CONFIGURATION  " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verification of Tailscale CLI
$tailscaleCmd = Get-Command "tailscale" -ErrorAction SilentlyContinue
if (-not $tailscaleCmd) {
    Write-Host "[WARNING] Tailscale CLI not found in PATH." -ForegroundColor Yellow
    Write-Host "Ensure Tailscale is installed from https://tailscale.com/download"
    Write-Host "After installing and logging in, re-run this script."
    exit 1
}

# 2. Security Check: Tailscale Funnel must NEVER be enabled
Write-Host "[SECURITY] Checking Tailscale Funnel status..." -ForegroundColor Gray
$funnelStatus = & tailscale funnel status 2>&1
if ($funnelStatus -match "active" -or $funnelStatus -match "enabled") {
    Write-Host "[CRITICAL SECURITY VIOLATION] Tailscale Funnel is currently active!" -ForegroundColor Red
    Write-Host "Disabling Tailscale Funnel immediately to prevent public internet exposure..." -ForegroundColor Yellow
    & tailscale funnel off
    Write-Host "[OK] Tailscale Funnel disabled. Workstation is private to your tailnet." -ForegroundColor Green
} else {
    Write-Host "[OK] Tailscale Funnel is DISABLED (Private tailnet ingress only)." -ForegroundColor Green
}

# 3. Security Check: Ollama port 11434 must NOT be exposed
Write-Host "[SECURITY] Verifying Ollama port 11434 isolation..." -ForegroundColor Gray
$ollamaListening = Get-NetTCPConnection -LocalPort 11434 -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" }
foreach ($conn in $ollamaListening) {
    if ($conn.LocalAddress -ne "127.0.0.1" -and $conn.LocalAddress -ne "::1") {
        Write-Host "[WARNING] Ollama listening on non-loopback address $($conn.LocalAddress)!" -ForegroundColor Red
    } else {
        Write-Host "[OK] Ollama port 11434 strictly isolated on $($conn.LocalAddress)." -ForegroundColor Green
    }
}

# 4. Configure Tailscale Serve for HTTPS 443 -> 127.0.0.1:8000
Write-Host ""
Write-Host "[CONFIGURE] Routing private Tailscale HTTPS 443 -> http://127.0.0.1:8000..." -ForegroundColor Cyan
& tailscale serve --bg --https 443 http://127.0.0.1:8000

# 5. Get Tailnet domain
$status = & tailscale status --json | ConvertFrom-Json
$nodeName = $status.Self.DNSName.TrimEnd(".")

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "  TAILSCALE SERVE ACTIVE & SECURED                   " -ForegroundColor Green
Write-Host "=====================================================" -ForegroundColor Green
Write-Host "Workstation Host: HP Victus 15 (Windows 11)"
Write-Host "Tailnet Node:     $nodeName"
Write-Host "Android PWA URL:  https://$nodeName/pwa/"
Write-Host "Dashboard URL:    https://$nodeName/dashboard/"
Write-Host ""
Write-Host "[CRITICAL OPERATIONAL NOTE]:" -ForegroundColor Yellow
Write-Host "The laptop is the AI host. If this HP Victus workstation is" -ForegroundColor Yellow
Write-Host "switched off, put to sleep, or disconnected from Tailscale," -ForegroundColor Yellow
Write-Host "local JARVIS cannot process requests and remote access is halted." -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Green
