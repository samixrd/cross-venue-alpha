$python = (Get-Command python).Source
$a = New-ScheduledTaskAction -Execute $python -Argument 'D:\cross-venue-alpha\tape\collector.py' -WorkingDirectory 'D:\cross-venue-alpha\tape'
$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Thursday -At 09:55PM
$s = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Days 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'VegaTape' -Action $a -Trigger $t -Settings $s -Force | Out-Null
Get-ScheduledTask -TaskName 'VegaTape' | Select-Object TaskName, State | Format-List

