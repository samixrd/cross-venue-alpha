$a = New-ScheduledTaskAction -Execute 'python' -Argument 'D:\cross-venue-alpha\research\snapshot.py' -WorkingDirectory 'D:\cross-venue-alpha\research'
$t = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Tuesday -At 09:00AM
Register-ScheduledTask -TaskName 'VegaSnapshot' -Action $a -Trigger $t -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable) -Force | Out-Null
Get-ScheduledTask -TaskName 'VegaSnapshot' | Select-Object TaskName, State | Format-List
