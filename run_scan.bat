@echo off
cd /d "%~dp0"
REM Runs one full scan of all enabled portals. Used by Windows Task Scheduler.
REM The dashboard does NOT need to be running for this to work.
".venv\Scripts\python.exe" main.py --scan
