# Simple Clean Diagnostic Script for ERA System

Write-Host "============================================================"
Write-Host "            ERA SYSTEM FULL DIAGNOSTIC & VERIFICATION       "
Write-Host "============================================================"
Write-Host ""

# 1. Health Check
Write-Host "[1/5] Checking Services Health..."

$agentOk = $false
try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8000/status" -TimeoutSec 3
    Write-Host "  [OK] Local Agent (8000): ONLINE - $($r.agent) (Commands: $($r.available_commands))"
    $agentOk = $true
} catch {
    Write-Host "  [FAIL] Local Agent (8000): DOWN"
}

$bridgeOk = $false
try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8100/v1/status" -TimeoutSec 3
    Write-Host "  [OK] Bridge Gateway (8100): ONLINE - $($r.status) (Version: $($r.bridge_version))"
    $bridgeOk = $true
} catch {
    Write-Host "  [FAIL] Bridge Gateway (8100): DOWN"
}

$visionOk = $false
try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:8200/v1/health" -TimeoutSec 3
    Write-Host "  [OK] Vision Agent (8200): ONLINE - $($r.service)"
    $visionOk = $true
} catch {
    Write-Host "  [FAIL] Vision Agent (8200): DOWN"
}

$uiOk = $false
try {
    $r = Invoke-RestMethod -Uri "http://127.0.0.1:3000/api/health" -TimeoutSec 3
    Write-Host "  [OK] Voice Assistant UI (3000): ONLINE - status: $($r.status)"
    $uiOk = $true
} catch {
    Write-Host "  [FAIL] Voice Assistant UI (3000): DOWN"
}

Write-Host ""

# 2. Test Command Execution via Bridge
Write-Host "[2/5] Testing Command Execution via ERA Bridge Gateway..."
try {
    $headers = @{
        "Content-Type" = "application/json"
        "X-Era-Bridge-Key" = "era_bridge_secret_key_2026"
    }
    $body = @{
        command = "get_peripheral_status"
        params = @{}
    } | ConvertTo-Json

    $res = Invoke-RestMethod -Uri "http://127.0.0.1:8100/v1/execute" -Method POST -Headers $headers -Body $body
    Write-Host "  [OK] Bridge Command Execution Result: State=$($res.state) Message='$($res.message)'"
} catch {
    Write-Host "  [FAIL] Bridge Command Execution Failed: $_"
}

Write-Host ""

# 3. Test ERA Vision Screen Perception via Bridge Passthrough
Write-Host "[3/5] Testing ERA Vision Screen Perception (ERA's Eyes)..."
try {
    $headers = @{
        "X-Era-Bridge-Key" = "era_bridge_secret_key_2026"
    }
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:8100/v1/vision/screen" -Headers $headers
    if ($res.current_state) {
        $cs = $res.current_state
        Write-Host "  [OK] ERA Vision is ACTIVE and watching screen!"
        Write-Host "     - Active App: $($cs.application)"
        Write-Host "     - Window Title: $($cs.window_title)"
        Write-Host "     - Summary: $($cs.summary)"
    } else {
        Write-Host "  [INFO] Vision Agent connected. Starting vision service..."
        $startRes = Invoke-RestMethod -Uri "http://127.0.0.1:8200/v1/vision/start" -Method POST -Headers @{"X-Vision-Agent-Key"="era_vision_secret_key_2026"}
        Write-Host "  [OK] Vision Service started: $($startRes.mode)"
    }
} catch {
    Write-Host "  [FAIL] Vision Screen Perception Check Failed: $_"
}

Write-Host ""

# 4. Summary
Write-Host "[4/5] Diagnostic Summary:"
if ($agentOk -and $bridgeOk -and $visionOk -and $uiOk) {
    Write-Host "  [SUCCESS] ALL 4 ERA SERVICES ARE ONLINE AND FULLY INTEGRATED!"
} else {
    Write-Host "  [WARNING] Some services are offline. Check individual logs."
}

Write-Host "============================================================"
