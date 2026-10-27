$shortcutPath = "C:\Users\MSI\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\ERA AI Assistant.lnk"
if (Test-Path $shortcutPath) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    Write-Host "TargetPath: $($shortcut.TargetPath)"
    Write-Host "Arguments: $($shortcut.Arguments)"
    Write-Host "WorkingDirectory: $($shortcut.WorkingDirectory)"
} else {
    Write-Host "Shortcut not found"
}
