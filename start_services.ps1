# ERA Independent Services Launcher
Write-Host "[ERA] Clearing old ports 8000, 8100, 8200, 3000..." -ForegroundColor Cyan
foreach ($port in @(8000, 8100, 8200, 3000)) {
    Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
        Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}
Start-Sleep -Seconds 2

$py = "d:\era_agent\.venv\Scripts\python.exe"

Write-Host "[ERA] Starting Agent on 8000..." -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList "-m uvicorn api_server:app --host 127.0.0.1 --port 8000 --log-level warning" -WorkingDirectory "d:\era_agent" -WindowStyle Hidden

Write-Host "[ERA] Starting Bridge on 8100..." -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList "main.py" -WorkingDirectory "d:\era_bridge\era_bridge" -WindowStyle Hidden

Write-Host "[ERA] Starting Vision on 8200..." -ForegroundColor Green
Start-Process -FilePath $py -ArgumentList "main.py" -WorkingDirectory "d:\era_vision\era_vision_agent_phase2\era_vision_agent" -WindowStyle Hidden

Start-Sleep -Seconds 4

Write-Host "[ERA] Starting Web UI on 3000..." -ForegroundColor Green
Start-Process -FilePath "cmd.exe" -ArgumentList "/c cd /d d:\era-voice-assistant && npx tsx server.ts" -WorkingDirectory "d:\era-voice-assistant" -WindowStyle Hidden

Start-Sleep -Seconds 5

Write-Host "`n[ERA] Checking service status..." -ForegroundColor Yellow
foreach ($s in @(
    @{ Name = "Local Agent"; Port = 8000 },
    @{ Name = "Bridge Gateway"; Port = 8100 },
    @{ Name = "Vision Agent"; Port = 8200 },
    @{ Name = "Web UI Server"; Port = 3000 }
)) {
    $c = Get-NetTCPConnection -LocalPort $s.Port -State Listen -ErrorAction SilentlyContinue
    if ($c) {
        Write-Host "  [OK] $($s.Name) is LISTENING on port $($s.Port) (PID $($c.OwningProcess))" -ForegroundColor Green
    } else {
        Write-Host "  [WAIT] $($s.Name) port $($s.Port) starting up..." -ForegroundColor Gray
    }
}
Write-Host "`n[ERA] Services launched successfully!`n" -ForegroundColor Cyan
