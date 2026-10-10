# Validate the real executable without modifying Bluetooth or dongle settings.
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    if (Get-Process FlooCast -ErrorAction SilentlyContinue) { throw 'Close existing FlooCast first.' }
    $flooTestProcess = Start-Process -FilePath .\dist\FlooCast.exe -ArgumentList '--show' -PassThru
    Start-Sleep -Seconds 10
    $initial = .\validate_windows_ui.ps1
    $initial | Set-Content -LiteralPath validation-packaged.txt
    $initial | Select-String 'Headset battery|streaming|Adaptive'
    .\validate_windows_ui.ps1 -Action Refresh
    $deadline = [DateTime]::UtcNow.AddSeconds(65)
    $fresh = $false
    $lastStatus = ''
    while ([DateTime]::UtcNow -lt $deadline) {
        $status = (.\validate_windows_ui.ps1 | Select-String '^Headset battery:').ToString()
        if ($status -ne $lastStatus) { Write-Output $status; $lastStatus = $status }
        if ($status -match '\d+%') { $fresh = $true; break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $fresh) { throw 'No live percentage returned after Refresh.' }
    .\validate_windows_ui.ps1 -Action Screenshot
    # No manual refresh here: observe the one-minute timer entering Reading.
    $deadline = [DateTime]::UtcNow.AddSeconds(65)
    $pollSeen = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $status = (.\validate_windows_ui.ps1 | Select-String '^Headset battery:').ToString()
        if ($status -ne $lastStatus) { Write-Output $status; $lastStatus = $status }
        if ($status -match 'Reading') { $pollSeen = $true; break }
        Start-Sleep -Milliseconds 500
    }
    Write-Output ('Automatic minute poll observed: ' + $pollSeen)
    .\validate_windows_ui.ps1 -Action Quit
    if (-not $flooTestProcess.WaitForExit(20000)) { throw 'FlooCast did not exit within 20 seconds.' }
    Write-Output ('Packaged executable exit code: ' + $flooTestProcess.ExitCode)
    if ($flooTestProcess.ExitCode -ne 0) { throw 'Nonzero executable exit code.' }
    .\.venv\Scripts\python.exe validate_hardware.py
    Get-FileHash -Algorithm SHA256 -LiteralPath dist\FlooCast.exe
    if (-not $pollSeen) { throw 'Automatic minute poll was not observed.' }
} finally {
    Pop-Location
}
