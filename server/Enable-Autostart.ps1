param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$entries = @{'Dross Translation Server' = 'Start-Server.ps1'}
$runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if ($Remove) {
    foreach ($name in @('Dross Translation Server', 'Dross Deck Link')) {
        Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
        Remove-ItemProperty -LiteralPath $runKey -Name $name -ErrorAction SilentlyContinue
    }
    Write-Output 'Dross automatic startup removed. Running processes are not stopped.'
    exit
}
if (Test-Path -LiteralPath (Join-Path $PSScriptRoot '.local/deck-link.json')) {
    $entries['Dross Deck Link'] = 'Start-Deck-Link.ps1'
}
foreach ($name in $entries.Keys) {
    $startScript = Join-Path $PSScriptRoot $entries[$name]
    $arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File `"$startScript`""
    try {
        $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description 'Local Dross service, starts after sign-in' -Force | Out-Null
        Remove-ItemProperty -LiteralPath $runKey -Name $name -ErrorAction SilentlyContinue
        Write-Output "$name enabled as a sign-in task."
    } catch {
        # Standard Windows accounts may not create Task Scheduler entries. The
        # per-user Startup mechanism needs no administrator rights or password.
        New-Item -Path $runKey -Force | Out-Null
        New-ItemProperty -LiteralPath $runKey -Name $name -Value "powershell.exe $arguments" -PropertyType String -Force | Out-Null
        Write-Output "$name enabled through per-user Windows Startup."
    }
}
