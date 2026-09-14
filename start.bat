@echo off
cd /d "%~dp0"
title Tender Monitor - FIND - TRACK - STAY AHEAD
if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found. Please run install.bat first.
  pause
  exit /b 1
)
echo ==================================================
echo     TENDER MONITOR
echo     FIND  -  TRACK  -  STAY AHEAD
echo ==================================================
echo.
echo Starting Tender Monitor ...
echo Dashboard: http://127.0.0.1:8000   (press Ctrl+C in this window to stop)
echo (The Tender Monitor logo appears in your browser tab and top bar.)
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" main.py --server
