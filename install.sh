#!/usr/bin/env bash
# Tender Monitor - installation for macOS / Linux
set -e
cd "$(dirname "$0")"
echo "=================================================="
echo "   Tender Monitor - Installation (macOS / Linux)"
echo "=================================================="
if ! command -v python3 >/dev/null 2>&1; then
  echo "[ERROR] python3 not found. Install Python 3.12+"
  echo "  macOS:  brew install python@3.12   (or https://www.python.org)"
  echo "  Linux:  use your package manager, e.g. sudo apt install python3 python3-venv"
  exit 1
fi
echo "[1/5] Creating virtual environment (.venv) ..."
python3 -m venv .venv
echo "[2/5] Upgrading pip ..."
./.venv/bin/python -m pip install --upgrade pip
echo "[3/5] Installing dependencies ..."
./.venv/bin/python -m pip install -r requirements.txt
echo "[4/5] Installing the Playwright Chromium browser ..."
./.venv/bin/python -m playwright install chromium
echo "[5/5] Initialising database and folders ..."
./.venv/bin/python -c "import config; config.ensure_directories(); from database.database import get_db; get_db(); print('Database ready at', config.DB_PATH)"
echo
echo "Installation complete."
echo "  Start the dashboard:  ./start.sh      (then open http://127.0.0.1:8000)"
echo "  Run a scan now:       ./run_scan.sh"
echo "  Schedule daily scans: ./setup_cron.sh"
