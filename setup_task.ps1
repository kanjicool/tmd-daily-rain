# setup_task.ps1
# สคริปต์สำหรับตั้งค่า Windows Task Scheduler อัตโนมัติ (Phase 3)
param(
    [string]$TaskName = "RunModel_Rain_0700",
    [string]$Time = "07:00:00"
)

$ScriptDir = $PSScriptRoot
if (Test-Path "C:\Users\ProDesk600\Desktop\runmodel") {
    $WorkingDir = "C:\Users\ProDesk600\Desktop\runmodel"
} else {
    $WorkingDir = $ScriptDir
}

$BatPath = Join-Path $WorkingDir "run_daily.bat"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " ตั้งค่า Windows Task Scheduler: $TaskName" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Script:    $BatPath"
Write-Host "Start in:  $WorkingDir"
Write-Host "Trigger:   ทุกวัน เวลา $Time"
Write-Host "------------------------------------------"

$Action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $WorkingDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $Time
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3) `
    -MultipleInstances IgnoreNew

try {
    # ลงทะเบียน Task สำหรับผู้ใช้ปัจจุบัน
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "ระบบดาวน์โหลดข้อมูลฝน TMD และรันโมเดลอัตโนมัติรายวัน (07:00 น.)" `
        -Force | Out-Null
    
    Write-Host "ลงทะเบียน Task Scheduler '$TaskName' สำเร็จเรียบร้อย!" -ForegroundColor Green
    Write-Host "คุณสามารถตรวจสอบหรือทดสอบ Run ได้จาก Task Scheduler หรือรันคำสั่ง:"
    Write-Host "Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Yellow
} catch {
    Write-Host "เกิดข้อผิดพลาดในการลงทะเบียน Task Scheduler: $_" -ForegroundColor Red
}
