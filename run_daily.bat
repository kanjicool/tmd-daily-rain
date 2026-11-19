@echo off
REM Change to working directory
if exist "C:\Users\ProDesk600\Desktop\runmodel" cd /d "C:\Users\ProDesk600\Desktop\runmodel"
if not exist "C:\Users\ProDesk600\Desktop\runmodel" cd /d "%~dp0"

echo [%date% %time%] start >> scheduler.log
python auto_run_daily.py >> scheduler.log 2>&1
set EXIT_CODE=%errorlevel%
echo [%date% %time%] exit code %EXIT_CODE% >> scheduler.log
exit /b %EXIT_CODE%
