#!/usr/bin/env bash
# Tender Monitor - start the local dashboard (macOS / Linux)
set -e
cd "$(dirname "$0")"
if [ ! -x ".venv/bin/python" ]; then
  echo "Virtual environment not found. Please run ./install.sh first."
  exit 1
fi
echo "=================================================="
echo "    TENDER MONITOR"
echo "    FIND  -  TRACK  -  STAY AHEAD"
echo "=================================================="
echo "Starting Tender Monitor ..."
echo "Dashboard: http://127.0.0.1:8000   (press Ctrl+C to stop)"
# Best-effort: open the browser after the server has a moment to start.
( sleep 2
  if command -v open >/dev/null 2>&1; then open http://127.0.0.1:8000
  elif command -v xdg-open >/dev/null 2>&1; then xdg-open http://127.0.0.1:8000
  fi ) >/dev/null 2>&1 &
exec ./.venv/bin/python main.py --server
