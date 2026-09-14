@echo off
echo Stopping Tender Monitor ...
taskkill /FI "WINDOWTITLE eq Tender Monitor" /T /F >nul 2>nul
if errorlevel 1 (
  echo No running Tender Monitor window was found.
  echo If the server is still running, switch to its console and press Ctrl+C.
) else (
  echo Tender Monitor stopped.
)
pause
