param([switch]$Remove)
$ErrorActionPreference = 'Stop'
$taskName = 'Dross Translation Server'
if ($Remove) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false; exit }
$startScript = Join-Path $PSScriptRoot 'Start-Server.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File `"$startScript`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Local-only Dross translation gateway, starts after sign-in'
