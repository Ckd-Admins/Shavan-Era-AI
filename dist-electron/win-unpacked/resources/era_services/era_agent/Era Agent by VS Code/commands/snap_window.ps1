param(
    [string]$AppName,
    [string]$Position,
    [string]$ResultFile
)

Add-Type -AssemblyName System.Windows.Forms
$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$W = $screen.Bounds.Width
$H = $screen.Bounds.Height
$halfW = [int]($W / 2)
$halfH = [int]($H / 2)

switch ($Position.ToLower().Trim()) {
    "left"         { $X=0;      $Y=0;      $CX=$halfW; $CY=$H }
    "right"        { $X=$halfW; $Y=0;      $CX=$halfW; $CY=$H }
    "top"          { $X=0;      $Y=0;      $CX=$W;     $CY=$halfH }
    "bottom"       { $X=0;      $Y=$halfH; $CX=$W;     $CY=$halfH }
    "top-left"     { $X=0;      $Y=0;      $CX=$halfW; $CY=$halfH }
    "top-right"    { $X=$halfW; $Y=0;      $CX=$halfW; $CY=$halfH }
    "bottom-left"  { $X=0;      $Y=$halfH; $CX=$halfW; $CY=$halfH }
    "bottom-right" { $X=$halfW; $Y=$halfH; $CX=$halfW; $CY=$halfH }
    "maximize"     { $X=$null }
    "minimize"     { $X=$null }
    "restore"      { $X=$null }
    default        { $X=0;      $Y=0;      $CX=$W;     $CY=$H }
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class WinPos {
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
}
"@ -ErrorAction SilentlyContinue

$AppNameLower = $AppName.ToLower().Trim()

# Build title-hint lookup
$titleHints = @{
    "whatsapp"         = @("whatsapp")
    "vscode"           = @("visual studio code")
    "code"             = @("visual studio code")
    "visual studio code" = @("visual studio code")
    "chrome"           = @("google chrome")
    "google chrome"    = @("google chrome")
    "edge"             = @("microsoft edge")
    "microsoft edge"   = @("microsoft edge")
    "msedge"           = @("microsoft edge")
    "firefox"          = @("mozilla firefox", "firefox")
    "notepad"          = @("notepad")
    "calculator"       = @("calculator")
    "explorer"         = @("file explorer")
    "store"            = @("microsoft store")
    "microsoft store"  = @("microsoft store")
    "xbox"             = @("xbox")
    "spotify"          = @("spotify")
    "discord"          = @("discord")
    "teams"            = @("microsoft teams")
}

if ($titleHints.ContainsKey($AppNameLower)) {
    $hints = $titleHints[$AppNameLower]
} else {
    $hints = @($AppNameLower)
}

# Find the process
$targetProc = $null
foreach ($hint in $hints) {
    $targetProc = Get-Process | Where-Object {
        $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -match [regex]::Escape($hint)
    } | Select-Object -First 1
    if ($targetProc) { break }
}

if (-not $targetProc) {
    $msg = "WINDOW_NOT_FOUND:$AppName"
    if ($ResultFile) { $msg | Set-Content -Path $ResultFile }
    Write-Output $msg
    exit 1
}

$hwnd = [IntPtr]$targetProc.MainWindowHandle

# Handle special positions
if ($Position.ToLower() -eq "maximize") {
    [WinPos]::ShowWindow($hwnd, 3) | Out-Null  # SW_MAXIMIZE
    $msg = "SUCCESS:$AppName maximized"
} elseif ($Position.ToLower() -eq "minimize") {
    [WinPos]::ShowWindow($hwnd, 6) | Out-Null  # SW_MINIMIZE
    $msg = "SUCCESS:$AppName minimized"
} elseif ($Position.ToLower() -eq "restore") {
    [WinPos]::ShowWindow($hwnd, 9) | Out-Null  # SW_RESTORE
    $msg = "SUCCESS:$AppName restored"
} else {
    [WinPos]::ShowWindow($hwnd, 9) | Out-Null  # SW_RESTORE first
    Start-Sleep -Milliseconds 300
    [WinPos]::SetWindowPos($hwnd, [IntPtr]::Zero, $X, $Y, $CX, $CY, 0x0044) | Out-Null
    [WinPos]::SetForegroundWindow($hwnd) | Out-Null
    $msg = "SUCCESS:$AppName snapped to $Position (x=$X,y=$Y,w=$CX,h=$CY) on ${W}x${H}"
}

if ($ResultFile) { $msg | Set-Content -Path $ResultFile }
Write-Output $msg
exit 0
