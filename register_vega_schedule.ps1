$r = New-ScheduledTaskAction -Execute 'python' -Argument 'D:\cross-venue-alpha\verification\vega_root.py root --date 2026-09-20' -WorkingDirectory 'D:\cross-venue-alpha\verification'
$rt = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 02:25PM
Register-ScheduledTask -TaskName 'VegaRoot' -Action $r -Trigger $rt -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable) -Force | Out-Null
$f = New-ScheduledTaskAction -Execute 'python' -Argument 'D:\cross-venue-alpha\verification\forward_readout.py' -WorkingDirectory 'D:\cross-venue-alpha\verification'
$ft = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 06:45PM
Register-ScheduledTask -TaskName 'VegaReadout' -Action $f -Trigger $ft -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable) -Force | Out-Null
Get-ScheduledTask -TaskName 'Vega*' | Select-Object TaskName, State | Format-Table -AutoSize
