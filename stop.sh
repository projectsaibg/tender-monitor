#!/usr/bin/env bash
# Tender Monitor - stop the local dashboard (macOS / Linux)
echo "Stopping Tender Monitor ..."
if pkill -f "main.py --server" 2>/dev/null; then
  echo "Tender Monitor stopped."
else
  echo "No running Tender Monitor server was found (it may already be stopped)."
fi
