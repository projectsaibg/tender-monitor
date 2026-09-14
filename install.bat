@echo off
setlocal
cd /d "%~dp0"
echo ==================================================
echo    Tender Monitor - Installation
echo ==================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  echo Install Python 3.12 or newer from https://www.python.org/downloads/
  echo Make sure to tick "Add Python to PATH" during installation.
  pause
  exit /b 1
)

echo [1/6] Creating virtual environment (.venv) ...
python -m venv .venv
if errorlevel 1 ( echo [ERROR] Could not create venv. & pause & exit /b 1 )

echo [2/6] Upgrading pip ...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo [3/6] Installing Python dependencies ...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo [ERROR] Dependency install failed. & pause & exit /b 1 )

echo [4/6] Installing the Playwright Chromium browser ...
".venv\Scripts\python.exe" -m playwright install chromium

echo [5/6] Creating folders and initializing the database ...
".venv\Scripts\python.exe" -c "import config; config.ensure_directories(); from database.database import get_db; get_db(); print('Database ready at', config.DB_PATH)"

echo [6/6] Done.
echo.
echo Installation complete.
echo   - Start the dashboard:  start.bat   (then open http://127.0.0.1:8000)
echo   - Run a scan now:       run_scan.bat
echo   - Schedule daily scans: setup_scheduler.bat
echo.
pause
