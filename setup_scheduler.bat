@echo off
setlocal
cd /d "%~dp0"
echo ==================================================
echo    Tender Monitor - Windows Task Scheduler setup
echo ==================================================
echo.
echo This creates a scheduled task that runs run_scan.bat every day,
echo scanning all enabled portals even when the dashboard is closed.
echo.
set /p RUNTIME="Enter daily scan time as HH:MM (default 07:00): "
if "%RUNTIME%"=="" set RUNTIME=07:00
set TASKNAME=TenderMonitorDaily

schtasks /Create /TN "%TASKNAME%" /TR "\"%~dp0run_scan.bat\"" /SC DAILY /ST %RUNTIME% /F
if errorlevel 1 (
  echo.
  echo [ERROR] Could not create the task. Try running this file as Administrator
  echo         (right-click setup_scheduler.bat - Run as administrator).
) else (
  echo.
  echo Created scheduled task "%TASKNAME%" to run daily at %RUNTIME%.
  echo To remove it later, run:  schtasks /Delete /TN %TASKNAME% /F
)
echo.
pause
